"""
Alltrax Toolkit settings importer.

Reads controller parameter files saved by Alltrax Toolkit and converts them
into an AlltraxSettings dataclass.  Supports three formats:

  1. Alltrax AEP / parameter file  — key=value pairs, one per line
       MaxCurrent=200
       AccelRate=120
       ThrottleMap=0,20,37,52,64,74,82,89,95,98,100
       ...

  2. Our own JSON export (from this app or from File → Save Settings)

  3. CSV key-value  (two columns: Parameter, Value)

Usage:
    from backend.analysis.alltrax_importer import import_alltrax_file
    settings, warnings = import_alltrax_file("controller_backup.aep")
"""

from __future__ import annotations
import json
import re
import csv
from pathlib import Path
from typing import Tuple, List

from backend.analysis.alltrax_settings import AlltraxSettings


# ---------------------------------------------------------------------------
# Key mapping  (Alltrax Toolkit key → AlltraxSettings field)
# ---------------------------------------------------------------------------

# All keys are normalised to lower-case, no spaces/underscores.
_KEY_MAP: dict[str, str] = {
    # Current
    "maxcurrent":          "max_current",
    "motorcurrentlimit":   "max_current",
    "motorcurrent":        "max_current",
    "peakcurrent":         "max_current",
    "currentlimit":        "max_current",
    # Accel / decel
    "accelrate":           "accel_rate",
    "accelerationrate":    "accel_rate",
    "rampup":              "accel_rate",
    "decelrate":           "decel_rate",
    "decelerationrate":    "decel_rate",
    "plugbrakerate":       "decel_rate",
    "rampdown":            "decel_rate",
    # Speed
    "speedlimit":          "speed_limit",
    "maxspeed":            "speed_limit",
    "topspeed":            "speed_limit",
    # Voltage
    "lowvoltcutoff":       "lo_voltage_cutoff",
    "lowvoltagecutoff":    "lo_voltage_cutoff",
    "undervoltage":        "lo_voltage_cutoff",
    "lvc":                 "lo_voltage_cutoff",
    "highvoltcutoff":      "hi_voltage_cutoff",
    "highvoltagecutoff":   "hi_voltage_cutoff",
    "overvoltage":         "hi_voltage_cutoff",
    "hvc":                 "hi_voltage_cutoff",
    # Throttle
    "throttledeadband":    "throttle_deadband",
    "deadband":            "throttle_deadband",
    "throttlemap":         "throttle_curve",
    "throttlecurve":       "throttle_curve",
    "throttle":            "throttle_curve",
    "map":                 "throttle_curve",
    # Peak amp mode
    "peakampmode":         "peak_amp_mode",
    "peakamps":            "peak_amp_mode",
    # Regen
    "regenbraking":        "regen_braking",
    "regenerativebraking": "regen_braking",
    "regen":               "regen_braking",
    "regenintensity":      "regen_intensity",
    "regenstrength":       "regen_intensity",
}


def _norm_key(key: str) -> str:
    return re.sub(r"[\s_\-]+", "", key.strip().lower())


def _parse_value(field: str, raw: str) -> object:
    """Convert a raw string value to the correct Python type for the field."""
    raw = raw.strip()

    if field == "throttle_curve":
        # Accept comma-separated list: "0,10,20,30,..."
        try:
            vals = [float(v.strip()) for v in raw.split(",")]
            # Normalise to 11 points if a different resolution was exported
            if len(vals) == 11:
                return vals
            if len(vals) > 2:
                import numpy as np
                x_old = [i * (100 / (len(vals) - 1)) for i in range(len(vals))]
                x_new = [i * 10 for i in range(11)]
                return [float(v) for v in np.interp(x_new, x_old, vals)]
        except ValueError:
            pass
        return AlltraxSettings().throttle_curve

    if field in ("peak_amp_mode", "regen_braking"):
        return raw.lower() in ("1", "true", "yes", "on", "enabled")

    # Numeric fields
    try:
        f = float(raw)
    except ValueError:
        return None

    if field in ("max_current", "accel_rate", "decel_rate",
                 "speed_limit", "throttle_deadband", "regen_intensity"):
        return int(round(f))

    return f   # float for voltages


# ---------------------------------------------------------------------------
# Format parsers
# ---------------------------------------------------------------------------

def _parse_aep(text: str) -> dict:
    """Parse Alltrax .aep / key=value parameter file."""
    params: dict[str, object] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";", "/", "[")):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        mapped = _KEY_MAP.get(_norm_key(key))
        if mapped:
            parsed = _parse_value(mapped, value)
            if parsed is not None:
                params[mapped] = parsed
    return params


def _parse_json(text: str) -> dict:
    """Parse our own JSON format."""
    d = json.loads(text)
    params: dict[str, object] = {}
    for raw_key, value in d.items():
        # Try direct field name first
        if raw_key in AlltraxSettings.__dataclass_fields__:
            params[raw_key] = value
        else:
            mapped = _KEY_MAP.get(_norm_key(raw_key))
            if mapped:
                parsed = _parse_value(mapped, str(value))
                if parsed is not None:
                    params[mapped] = parsed
    return params


def _parse_csv_kv(text: str) -> dict:
    """Parse CSV with two columns: Parameter, Value."""
    params: dict[str, object] = {}
    reader = csv.reader(text.splitlines())
    for row in reader:
        if len(row) < 2:
            continue
        key, value = row[0], row[1]
        mapped = _KEY_MAP.get(_norm_key(key))
        if mapped:
            parsed = _parse_value(mapped, value)
            if parsed is not None:
                params[mapped] = parsed
    return params


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def import_alltrax_file(filepath: str) -> Tuple[AlltraxSettings, List[str]]:
    """
    Read an Alltrax parameter file and return (AlltraxSettings, warnings).

    Supports .aep, .json, .txt, .csv.
    Unrecognised parameters are ignored with a warning.
    """
    path = Path(filepath)
    warnings: List[str] = []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise ValueError(f"Cannot read file: {e}") from e

    # Detect format
    suffix = path.suffix.lower()
    params: dict = {}

    if suffix == ".json":
        try:
            params = _parse_json(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

    elif suffix == ".csv":
        params = _parse_csv_kv(text)
        if not params:
            # Maybe it's actually key=value in a CSV
            params = _parse_aep(text)

    else:
        # .aep, .txt, or unknown — try AEP first, then JSON fallback
        params = _parse_aep(text)
        if not params:
            try:
                params = _parse_json(text)
            except Exception:
                pass

    if not params:
        raise ValueError(
            "No recognisable Alltrax parameters found in the file.\n"
            "Expected key=value pairs (e.g. MaxCurrent=200) or JSON format."
        )

    # Start from defaults and overlay what we parsed
    base = AlltraxSettings()
    recognised = set(AlltraxSettings.__dataclass_fields__.keys())

    applied = []
    for field_name, value in params.items():
        if field_name in recognised:
            setattr(base, field_name, value)
            applied.append(field_name)

    if not applied:
        warnings.append("File was read but no matching parameters were found. Check the format.")
    else:
        warnings.append(f"Imported {len(applied)} parameters: {', '.join(sorted(applied))}.")

    # Post-import sanity checks
    if base.max_current > 220:
        warnings.append(
            f"⛔ RULE VIOLATION: Imported max_current={base.max_current} A exceeds the "
            f"EVGP 220 A limit. The value has been clamped to 220 A."
        )
        base.max_current = 220

    if base.hi_voltage_cutoff > 58.4:
        warnings.append(
            f"⚠ hi_voltage_cutoff={base.hi_voltage_cutoff} V exceeds 58.4 V (LiFePO4 max). "
            "Clamped to 58.4 V."
        )
        base.hi_voltage_cutoff = 58.4

    if base.lo_voltage_cutoff < 40.0:
        warnings.append(
            f"⚠ lo_voltage_cutoff={base.lo_voltage_cutoff} V is below 40.0 V (LiFePO4 min). "
            "Clamped to 40.0 V."
        )
        base.lo_voltage_cutoff = 40.0

    return base, warnings


def export_alltrax_aep(settings: AlltraxSettings, filepath: str) -> None:
    """
    Write settings to an Alltrax-compatible .aep parameter file.
    Can be loaded back into Alltrax Toolkit via File → Load Settings.
    """
    curve_str = ",".join(str(int(round(v))) for v in settings.throttle_curve)
    lines = [
        "# Alltrax Parameter File — generated by EV Kart Data Analyzer",
        f"MaxCurrent={settings.max_current}",
        f"AccelRate={settings.accel_rate}",
        f"DecelRate={settings.decel_rate}",
        f"SpeedLimit={settings.speed_limit}",
        f"LowVoltCutoff={settings.lo_voltage_cutoff:.1f}",
        f"HighVoltCutoff={settings.hi_voltage_cutoff:.1f}",
        f"ThrottleDeadband={settings.throttle_deadband}",
        f"PeakAmpMode={'1' if settings.peak_amp_mode else '0'}",
        f"RegenBraking={'1' if settings.regen_braking else '0'}",
        f"RegenIntensity={settings.regen_intensity}",
        f"ThrottleMap={curve_str}",
    ]
    Path(filepath).write_text("\n".join(lines) + "\n")
