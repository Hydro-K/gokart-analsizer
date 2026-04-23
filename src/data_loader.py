"""
AiM Solo 2 CSV parser and raw session data model.
Handles multiple AiM export format variations.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class RawSessionData:
    time: np.ndarray        # seconds
    speed: np.ndarray       # m/s
    lat: np.ndarray         # degrees (may be zeros if not available)
    lon: np.ndarray         # degrees (may be zeros if not available)
    beacon: np.ndarray      # 0/1 lap trigger pulses
    has_gps: bool
    has_beacon: bool
    filename: str
    driver_name: str = "Driver"
    sample_rate: float = 10.0  # Hz


_AIM_META_PREFIXES = (
    "format", "firmware", "date", "time", "vehicle", "racer",
    "venue", "championship", "comment", "device", "channel",
)

_SPEED_ALIASES = [
    "gps speed", "gps_speed", "speed", "gps vel", "velocity",
    "ground speed", "vgps", "v gps", "kart speed",
]
_TIME_ALIASES = ["time", "t", "elapsed", "elapsed time"]
_LAT_ALIASES = ["gps lat", "gps_lat", "latitude", "lat"]
_LON_ALIASES = ["gps lon", "gps_lon", "longitude", "lon", "lng"]
_BEACON_ALIASES = ["beacon", "lap beacon", "lap trigger", "lap", "lap_beacon"]


def _normalise_col(name: str) -> str:
    return re.sub(r"[\s_\-]+", " ", name.strip().lower())


def _find_col(columns: list[str], aliases: list[str]) -> Optional[str]:
    norm = {_normalise_col(c): c for c in columns}
    for alias in aliases:
        if alias in norm:
            return norm[alias]
    return None


def _detect_header_rows(filepath: str) -> tuple[int, int]:
    """Return (data_header_row, skip_rows) for pd.read_csv."""
    with open(filepath, "r", errors="replace") as f:
        lines = [f.readline() for _ in range(40)]

    # Find first line whose first token looks like a column header (Time / GPS Speed / etc.)
    for i, line in enumerate(lines):
        first = line.split(",")[0].strip().strip('"').lower()
        if first in ("time", "t", "elapsed"):
            return i, i  # header is on row i
        # AiM sometimes has index column before time
        tokens = [t.strip().strip('"').lower() for t in line.split(",")]
        if "time" in tokens or "gps speed" in tokens:
            return i, i

    return 0, 0


def load_aim_csv(filepath: str) -> RawSessionData:
    """
    Load an AiM Solo 2 CSV export.  Returns a RawSessionData with time (s)
    and speed (m/s).  Tolerates most AiM export format variants.
    """
    filepath = str(filepath)

    header_row, _ = _detect_header_rows(filepath)

    # Use skiprows so blank lines before the header don't shift pandas' row count
    df = pd.read_csv(
        filepath,
        skiprows=range(header_row),
        header=0,
        skip_blank_lines=False,
        on_bad_lines="skip",
        encoding_errors="replace",
    )
    # Drop purely blank rows that slipped through
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Drop rows that look like units (e.g. "s", "km/h", "deg")
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    first_data_row = df.iloc[0]
    unit_like = re.compile(r"^(s|ms|km/h|m/s|mph|deg|m|g|rpm|%|v|a|bar|°c|hz)$", re.I)
    if all(
        unit_like.match(str(v).strip()) or str(v).strip() == ""
        for v in first_data_row
        if str(v).strip()
    ):
        df = df.iloc[1:].reset_index(drop=True)

    # Force numeric
    df = df.apply(pd.to_numeric, errors="coerce")
    df.dropna(how="all", inplace=True)

    cols = list(df.columns)

    time_col = _find_col(cols, _TIME_ALIASES)
    speed_col = _find_col(cols, _SPEED_ALIASES)
    lat_col = _find_col(cols, _LAT_ALIASES)
    lon_col = _find_col(cols, _LON_ALIASES)
    beacon_col = _find_col(cols, _BEACON_ALIASES)

    if time_col is None:
        # Assume first numeric column is time
        time_col = cols[0]
    if speed_col is None:
        # Assume second numeric column is speed
        speed_col = cols[1] if len(cols) > 1 else cols[0]

    time = df[time_col].to_numpy(dtype=float)
    speed_raw = df[speed_col].to_numpy(dtype=float)

    # Detect and convert units: if max speed > 200 assume km/h; if > 300 assume mph
    if np.nanmax(speed_raw) > 300:
        speed_ms = speed_raw * 0.44704  # mph -> m/s
    elif np.nanmax(speed_raw) > 10:
        speed_ms = speed_raw / 3.6  # km/h -> m/s
    else:
        speed_ms = speed_raw  # already m/s

    # Fill NaN in speed with interpolation
    nan_mask = np.isnan(speed_ms)
    if nan_mask.any():
        idx = np.arange(len(speed_ms))
        speed_ms[nan_mask] = np.interp(idx[nan_mask], idx[~nan_mask], speed_ms[~nan_mask])

    nan_mask_t = np.isnan(time)
    if nan_mask_t.any():
        idx = np.arange(len(time))
        time[nan_mask_t] = np.interp(idx[nan_mask_t], idx[~nan_mask_t], time[~nan_mask_t])

    has_gps = lat_col is not None and lon_col is not None
    lat = df[lat_col].to_numpy(dtype=float) if has_gps else np.zeros(len(time))
    lon = df[lon_col].to_numpy(dtype=float) if has_gps else np.zeros(len(time))

    has_beacon = beacon_col is not None
    if has_beacon:
        beacon_raw = df[beacon_col].fillna(0).to_numpy(dtype=float)
        # Convert to binary pulses
        beacon = (beacon_raw > 0.5).astype(float)
    else:
        beacon = np.zeros(len(time))

    dt = np.diff(time)
    sample_rate = 1.0 / np.median(dt[dt > 0]) if len(dt) > 0 else 10.0

    return RawSessionData(
        time=time,
        speed=speed_ms,
        lat=lat,
        lon=lon,
        beacon=beacon,
        has_gps=has_gps,
        has_beacon=has_beacon,
        filename=Path(filepath).name,
        sample_rate=round(sample_rate, 1),
    )
