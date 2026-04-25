"""
AiM Solo 2 / SCCA CSV parser.

Handles every known AiM Race Studio 3 export variant:
  • Multi-line metadata header (Format / Firmware / Date / Vehicle / Racer / …)
  • Units row immediately after column-name row
  • Quoted column names ("GPS Speed" with quotes)
  • Leading unnamed index column (AiM sometimes prepends a row-number column)
  • Windows CRLF and UTF-8-BOM encodings
  • km/h or mph speed channels
  • Multiple GPS channel naming conventions used across Race Studio versions
  • Millisecond vs second time columns

Returns a RawSessionData with time in seconds, speed in m/s.
A DataQualityWarning string list is attached for the GUI to display.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Column alias tables — ordered by priority (first match wins)
# ---------------------------------------------------------------------------

# --- Time ---
_TIME_ALIASES = [
    "time", "t", "elapsed time", "elapsed", "timestamp",
    "gps time", "sample time", "time (s)", "time(s)",
]

# --- Speed ---
# AiM Race Studio exports GPS speed as "GPS Speed" (km/h by default).
# Some older firmware exports it as "Vel." or "GPS Vel."
_SPEED_ALIASES = [
    "gps speed", "gpsSpeed", "gps vel", "gps vel.", "gps velocity",
    "speed", "velocity", "vel", "ground speed",
    "vgps", "v gps", "spd", "kart speed",
    "gps spd", "gps_speed", "gps_vel",
]

# --- GPS ---
_LAT_ALIASES = [
    "gps lat", "gps lat.", "gps latitude", "latitude", "lat",
    "gps_lat", "lat.", "gpslatitude", "gpslat",
]
_LON_ALIASES = [
    "gps lon", "gps lon.", "gps long", "gps longitude", "longitude",
    "lon", "lng", "long", "gps_lon", "lon.", "gpslongitude", "gpslon",
]
_ALT_ALIASES = [
    "gps alt", "gps alt.", "gps altitude", "altitude", "alt",
    "gps_alt", "alt.", "gpsaltitude",
]

# --- Lap beacon ---
_BEACON_ALIASES = [
    "gps beacon", "beacon", "lap beacon", "lap trigger", "lap",
    "lap_beacon", "gps_beacon", "beaconpulse", "trigger",
    "lap signal", "lap flag", "lapflag",
]

# AiM metadata key prefixes (lines to skip before the data header)
_META_KEYS = frozenset([
    "format", "firmware", "date", "time", "vehicle", "racer",
    "venue", "championship", "comment", "device", "channel",
    "driver", "logger", "software", "session",
])

# Unit strings that appear in the units row
_UNIT_RE = re.compile(
    r"^(s|ms|sec|seconds|km/h|kph|m/s|mph|deg|degree|degrees|m|mm|"
    r"g|rpm|%|v|volts|a|amps|bar|psi|°c|hz|n|nm|mbar|hpa)$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class RawSessionData:
    time:        np.ndarray         # seconds
    speed:       np.ndarray         # m/s
    lat:         np.ndarray         # degrees (zeros if no GPS)
    lon:         np.ndarray         # degrees
    beacon:      np.ndarray         # 0/1 lap trigger pulses
    has_gps:     bool
    has_beacon:  bool
    filename:    str
    driver_name: str = "Driver"
    sample_rate: float = 10.0       # Hz
    warnings:    List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    """Normalise a column name for alias matching."""
    return re.sub(r"[\s_\-./()]+", " ", name.strip().strip('"').lower()).strip()


def _find_col(columns: List[str], aliases: List[str]) -> Optional[str]:
    norm_map = {_norm(c): c for c in columns}
    for alias in aliases:
        if alias in norm_map:
            return norm_map[alias]
    return None


def _is_unit_row(row: pd.Series) -> bool:
    """True if every non-empty cell looks like a physical unit string."""
    values = [str(v).strip() for v in row if str(v).strip() not in ("", "nan")]
    if not values:
        return True   # all empty → treat as blank / unit-like
    return all(_UNIT_RE.match(v) for v in values)


def _find_header_row(filepath: str) -> int:
    """
    Read up to 50 lines and return the line index (0-based) of the row
    that contains the column headers.  Heuristic: first row whose first
    token is 'time' (or another time alias), or that contains both a
    time alias and a speed alias.
    """
    time_set  = set(_TIME_ALIASES)
    speed_set = set(_SPEED_ALIASES)

    try:
        with open(filepath, "r", errors="replace", newline="") as f:
            lines = [f.readline() for _ in range(60)]
    except OSError:
        return 0

    for i, line in enumerate(lines):
        if not line.strip():
            continue
        raw_tokens = line.split(",")
        tokens = [_norm(t) for t in raw_tokens]

        # First token is a time alias → this is the header row
        if tokens and tokens[0] in time_set:
            return i

        # Header row may have a leading empty index column
        non_empty = [t for t in tokens if t]
        if non_empty and non_empty[0] in time_set:
            return i

        # Row contains both time AND speed aliases → header
        if any(t in time_set for t in tokens) and any(t in speed_set for t in tokens):
            return i

    return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_aim_csv(filepath: str) -> RawSessionData:
    """
    Parse an AiM Solo 2 (or compatible SCCA export) CSV.
    Returns RawSessionData with time in seconds and speed in m/s.
    Attaches a `warnings` list of human-readable quality notes.
    """
    filepath = str(filepath)
    warnings: List[str] = []

    header_row = _find_header_row(filepath)

    # Read the file, skipping all pre-header metadata rows
    df = pd.read_csv(
        filepath,
        skiprows=range(header_row),
        header=0,
        skip_blank_lines=False,          # preserve row count alignment
        on_bad_lines="skip",
        encoding_errors="replace",
        dtype=str,                        # read everything as string first
    )

    # ---- 1. Normalise column names ---------------------------------
    df.columns = [str(c).strip().strip('"') for c in df.columns]

    # Drop leading unnamed index column AiM sometimes adds
    if df.columns[0].startswith("Unnamed") or df.columns[0].strip() == "":
        df = df.iloc[:, 1:]

    # ---- 2. Drop units row (immediately after header) --------------
    if len(df) > 0 and _is_unit_row(df.iloc[0]):
        df = df.iloc[1:].reset_index(drop=True)

    # Drop fully blank rows
    df.replace("", np.nan, inplace=True)
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # ---- 3. Coerce everything to numeric ---------------------------
    df = df.apply(pd.to_numeric, errors="coerce")
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    if len(df) == 0:
        raise ValueError(
            "No numeric data found after header row.  "
            "Check that the file is a valid AiM Race Studio 3 CSV export."
        )

    cols = list(df.columns)

    # ---- 4. Identify channels --------------------------------------
    time_col   = _find_col(cols, _TIME_ALIASES)
    speed_col  = _find_col(cols, _SPEED_ALIASES)
    lat_col    = _find_col(cols, _LAT_ALIASES)
    lon_col    = _find_col(cols, _LON_ALIASES)
    beacon_col = _find_col(cols, _BEACON_ALIASES)

    # Fallbacks: use first / second numeric column
    if time_col is None:
        time_col = cols[0]
        warnings.append(
            f"No 'Time' column found — using '{time_col}' as time. "
            "Verify this is in seconds."
        )
    if speed_col is None and len(cols) > 1:
        speed_col = cols[1]
        warnings.append(
            f"No speed channel found — using '{speed_col}'. "
            "Verify this is GPS speed in km/h or m/s."
        )

    # ---- 5. Extract arrays -----------------------------------------
    time_raw  = df[time_col].to_numpy(dtype=float)
    speed_raw = df[speed_col].to_numpy(dtype=float) if speed_col else np.zeros(len(time_raw))

    # Fill internal NaNs by linear interpolation
    def _interp_nan(arr: np.ndarray) -> np.ndarray:
        arr = arr.copy()
        nans = np.isnan(arr)
        if nans.any() and (~nans).sum() >= 2:
            idx = np.arange(len(arr))
            arr[nans] = np.interp(idx[nans], idx[~nans], arr[~nans])
        elif nans.any():
            arr[nans] = 0.0
        return arr

    time_raw  = _interp_nan(time_raw)
    speed_raw = _interp_nan(speed_raw)

    # ---- 6. Unit detection for time --------------------------------
    # If time values are in milliseconds (first sample > 1000) convert to seconds
    if len(time_raw) > 1 and time_raw[1] > 500:
        time_raw = time_raw / 1000.0
        warnings.append("Time channel appears to be in milliseconds — auto-converted to seconds.")

    # ---- 7. Unit detection for speed -------------------------------
    speed_max = float(np.nanmax(speed_raw))
    if speed_max > 300:
        # mph
        speed_ms = speed_raw * 0.44704
        warnings.append(f"Speed channel max {speed_max:.0f} — interpreted as mph.")
    elif speed_max > 8:
        # km/h (AiM default)
        speed_ms = speed_raw / 3.6
    else:
        # already m/s
        speed_ms = speed_raw
        warnings.append(f"Speed channel max {speed_max:.2f} — interpreted as m/s.")

    # ---- 8. GPS ----------------------------------------------------
    has_gps = lat_col is not None and lon_col is not None
    lat = _interp_nan(df[lat_col].to_numpy(dtype=float)) if has_gps else np.zeros(len(time_raw))
    lon = _interp_nan(df[lon_col].to_numpy(dtype=float)) if has_gps else np.zeros(len(time_raw))

    # Sanity-check GPS values
    if has_gps:
        if np.all(lat == 0) and np.all(lon == 0):
            has_gps = False
            warnings.append("GPS columns present but all zeros — treating as no GPS.")
        elif not (-90 <= np.nanmean(lat) <= 90):
            has_gps = False
            warnings.append("GPS latitude values out of range — ignoring GPS.")

    # ---- 9. Beacon -------------------------------------------------
    has_beacon = beacon_col is not None
    if has_beacon:
        b_raw  = df[beacon_col].fillna(0).to_numpy(dtype=float)
        beacon = (b_raw > 0.5).astype(float)
        if beacon.sum() == 0:
            has_beacon = False
            warnings.append("Beacon column found but no pulses detected — using speed-based lap detection.")
    else:
        beacon = np.zeros(len(time_raw))
        warnings.append("No beacon/lap-trigger channel found — using speed-based lap detection.")

    # ---- 10. Sample rate -------------------------------------------
    dt = np.diff(time_raw)
    dt_pos = dt[dt > 0]
    sample_rate = round(1.0 / float(np.median(dt_pos)), 1) if len(dt_pos) else 10.0

    # ---- 11. Data quality checks -----------------------------------
    if len(time_raw) < 100:
        warnings.append(f"Only {len(time_raw)} samples — file may be truncated.")
    if speed_ms.max() < 1.0:
        warnings.append("Max speed < 1 m/s — kart may not have moved or wrong column selected.")
    if sample_rate < 1 or sample_rate > 500:
        warnings.append(f"Unusual sample rate detected: {sample_rate} Hz.")

    return RawSessionData(
        time=time_raw,
        speed=speed_ms,
        lat=lat,
        lon=lon,
        beacon=beacon,
        has_gps=has_gps,
        has_beacon=has_beacon,
        filename=Path(filepath).name,
        sample_rate=sample_rate,
        warnings=warnings,
    )
