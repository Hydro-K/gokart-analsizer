"""
Alltrax SR-72400 motor controller settings model.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class AlltraxSettings:
    max_current: int = 300          # 0–400 A
    accel_rate: int = 64            # 1–255  (higher = faster ramp)
    decel_rate: int = 64            # 1–255  (plug/regen braking strength)
    speed_limit: int = 100          # 0–100 %
    lo_voltage_cutoff: float = 30.0 # volts (LiPo pack low-cell protection)
    hi_voltage_cutoff: float = 58.8 # volts (full-charge BMS limit)
    throttle_deadband: int = 10     # 0–255 (raw ADC counts)
    peak_amp_mode: bool = True      # True = allow peak amps above map limit
    regen_braking: bool = False     # True = regenerative braking enabled
    regen_intensity: int = 40       # 0–100 % regen strength
    throttle_curve: List[float] = field(
        default_factory=lambda: [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    )  # 11 points: output % at throttle input 0,10,20,...,100 %

    # ---- Presets --------------------------------------------------------

    THROTTLE_PRESETS = {
        "Linear": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        "Aggressive": [0, 20, 37, 52, 64, 74, 82, 89, 95, 98, 100],
        "Soft S-Curve": [0, 2, 8, 18, 32, 50, 68, 82, 92, 98, 100],
        "Late Apex": [0, 5, 11, 18, 27, 38, 52, 68, 82, 93, 100],
    }

    # ---- I/O ------------------------------------------------------------

    def to_json(self, filepath: str) -> None:
        with open(filepath, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def from_json(cls, filepath: str) -> "AlltraxSettings":
        with open(filepath, "r") as f:
            d = json.load(f)
        return cls(**d)

    def copy(self) -> "AlltraxSettings":
        import copy
        return copy.deepcopy(self)

    # ---- Helpers --------------------------------------------------------

    def throttle_output_at(self, input_pct: float) -> float:
        """Interpolate throttle curve. input_pct in [0, 100]."""
        import numpy as np
        x = [i * 10 for i in range(len(self.throttle_curve))]
        return float(np.interp(input_pct, x, self.throttle_curve))
