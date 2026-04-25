"""
Session telemetry logger.
Records post-session readings: tyre temps/PSI, motor, battery, brake temps.
All values optional so the form can be partially filled.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List


# ---------------------------------------------------------------------------
# Warning / danger thresholds for each sensor class
# Green = normal, Yellow = watch it, Red = act now
# ---------------------------------------------------------------------------
THRESHOLDS = {
    # kart tyre temps (°C) – typical MG Yellow / Bridgestone race kart
    "tyre_temp":        {"lo_warn": 55,  "lo_ok": 70,  "hi_ok": 95,  "hi_warn": 110},
    # motor winding temp (°C)
    "motor_temp":       {"lo_warn": 0,   "lo_ok": 10,  "hi_ok": 75,  "hi_warn": 95},
    # Alltrax controller case temp (°C)
    "controller_temp":  {"lo_warn": 0,   "lo_ok": 10,  "hi_ok": 65,  "hi_warn": 85},
    # LiPo battery pack temp (°C)
    "battery_temp":     {"lo_warn": 0,   "lo_ok": 10,  "hi_ok": 40,  "hi_warn": 55},
    # Kart disc / drum brake temps (°C) – colder than car brakes
    "brake_temp":       {"lo_warn": 30,  "lo_ok": 80,  "hi_ok": 350, "hi_warn": 500},
    # Tyre cold PSI – typical kart road tyre
    "tyre_psi":         {"lo_warn": 10,  "lo_ok": 14,  "hi_ok": 19,  "hi_warn": 22},
    # LiPo 14S pack voltage (50.4 V full, 44.8 V nominal, 39.2 V empty)
    "battery_voltage":  {"lo_warn": 42,  "lo_ok": 45,  "hi_ok": 58,  "hi_warn": 60},
}


def temp_status(value: Optional[float], key: str) -> str:
    """Return 'ok' | 'warn_lo' | 'warn_hi' | 'danger_lo' | 'danger_hi' | 'unknown'."""
    if value is None:
        return "unknown"
    t = THRESHOLDS.get(key, {})
    if not t:
        return "ok"
    if value < t["lo_warn"]:
        return "danger_lo"
    if value < t["lo_ok"]:
        return "warn_lo"
    if value > t["hi_warn"]:
        return "danger_hi"
    if value > t["hi_ok"]:
        return "warn_hi"
    return "ok"


STATUS_COLORS = {
    "ok":        "#00FF88",
    "warn_lo":   "#FFD700",
    "warn_hi":   "#FFD700",
    "danger_lo": "#FF4444",
    "danger_hi": "#FF4444",
    "unknown":   "#555577",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

SESSION_TYPES = [
    "Practice 1", "Practice 2", "Practice 3",
    "Qualifying 1", "Qualifying 2",
    "Heat Race", "Main Race", "Endurance", "Shakedown", "Testing",
]

TRACK_CONDITIONS = ["Dry", "Damp", "Wet", "Greasy", "Unknown"]


@dataclass
class TelemetryReading:
    """One post-session telemetry snapshot.  All sensor fields are Optional."""

    # --- Identity --------------------------------------------------------
    timestamp: str = ""
    session_type: str = "Practice 1"
    track: str = ""
    data_file: str = ""                  # linked AiM CSV path (for reload)

    # --- Session results -------------------------------------------------
    best_lap_time_s: Optional[float] = None
    num_laps: Optional[int] = None
    track_condition: str = "Dry"
    ambient_temp_c: Optional[float] = None
    track_temp_c: Optional[float] = None
    humidity_pct: Optional[float] = None

    # --- Tyre temperatures (°C) — measured immediately after session -----
    tyre_temp_fl: Optional[float] = None   # Front Left
    tyre_temp_fr: Optional[float] = None   # Front Right
    tyre_temp_rl: Optional[float] = None   # Rear Left
    tyre_temp_rr: Optional[float] = None   # Rear Right

    # --- Tyre pressures (PSI, cold — measured before session) ------------
    tyre_psi_fl: Optional[float] = None
    tyre_psi_fr: Optional[float] = None
    tyre_psi_rl: Optional[float] = None
    tyre_psi_rr: Optional[float] = None

    # --- Motor / controller (°C) -----------------------------------------
    motor_temp_c: Optional[float] = None
    controller_temp_c: Optional[float] = None

    # --- Battery ---------------------------------------------------------
    battery_temp_c: Optional[float] = None
    battery_voltage_v: Optional[float] = None    # pack voltage at rest after session
    battery_soc_pct: Optional[float] = None      # estimated state-of-charge

    # --- Brake temps (°C) — measured immediately after session -----------
    brake_temp_fl: Optional[float] = None
    brake_temp_fr: Optional[float] = None
    brake_temp_rl: Optional[float] = None
    brake_temp_rr: Optional[float] = None

    # --- Gear / setup snapshot ------------------------------------------
    motor_sprocket: Optional[int] = None
    axle_sprocket: Optional[int] = None
    max_current_a: Optional[int] = None

    # --- Free notes ------------------------------------------------------
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    @property
    def best_lap_str(self) -> str:
        if self.best_lap_time_s is None:
            return "—"
        m = int(self.best_lap_time_s // 60)
        s = self.best_lap_time_s % 60
        return f"{m}:{s:06.3f}"

    def statuses(self) -> dict[str, str]:
        """Return {field_name: status_str} for every sensor field."""
        return {
            "tyre_temp_fl":     temp_status(self.tyre_temp_fl,     "tyre_temp"),
            "tyre_temp_fr":     temp_status(self.tyre_temp_fr,     "tyre_temp"),
            "tyre_temp_rl":     temp_status(self.tyre_temp_rl,     "tyre_temp"),
            "tyre_temp_rr":     temp_status(self.tyre_temp_rr,     "tyre_temp"),
            "tyre_psi_fl":      temp_status(self.tyre_psi_fl,      "tyre_psi"),
            "tyre_psi_fr":      temp_status(self.tyre_psi_fr,      "tyre_psi"),
            "tyre_psi_rl":      temp_status(self.tyre_psi_rl,      "tyre_psi"),
            "tyre_psi_rr":      temp_status(self.tyre_psi_rr,      "tyre_psi"),
            "motor_temp_c":     temp_status(self.motor_temp_c,     "motor_temp"),
            "controller_temp_c":temp_status(self.controller_temp_c,"controller_temp"),
            "battery_temp_c":   temp_status(self.battery_temp_c,   "battery_temp"),
            "battery_voltage_v":temp_status(self.battery_voltage_v,"battery_voltage"),
            "brake_temp_fl":    temp_status(self.brake_temp_fl,    "brake_temp"),
            "brake_temp_fr":    temp_status(self.brake_temp_fr,    "brake_temp"),
            "brake_temp_rl":    temp_status(self.brake_temp_rl,    "brake_temp"),
            "brake_temp_rr":    temp_status(self.brake_temp_rr,    "brake_temp"),
        }


# SessionDatabase removed — persistence now handled by SQLite via post_session_readings table
