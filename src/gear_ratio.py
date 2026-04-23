"""
Gear ratio calculator and top-speed predictor.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, asdict


@dataclass
class GearRatioConfig:
    motor_sprocket_teeth: int = 11      # teeth on motor output sprocket
    axle_sprocket_teeth: int = 72       # teeth on rear axle sprocket
    tire_diameter_in: float = 11.0      # rear tire diameter in inches
    motor_rpm_max: int = 5500           # estimated motor free-running RPM at full charge

    @property
    def ratio(self) -> float:
        """Reduction ratio: axle_teeth / motor_teeth.  >1 means reduction."""
        return self.axle_sprocket_teeth / max(1, self.motor_sprocket_teeth)

    @property
    def tire_circumference_m(self) -> float:
        return self.tire_diameter_in * 0.0254 * 3.14159

    def top_speed_ms(self) -> float:
        """Theoretical top speed in m/s."""
        wheel_rpm = self.motor_rpm_max / self.ratio
        wheel_rps = wheel_rpm / 60.0
        return wheel_rps * self.tire_circumference_m

    def top_speed_kmh(self) -> float:
        return self.top_speed_ms() * 3.6

    def projected_top_speed_kmh(self, observed_max_kmh: float, new_config: "GearRatioConfig") -> float:
        """Project top speed for a new gear config, anchored to observed data."""
        scale = self.ratio / new_config.ratio
        return observed_max_kmh * scale

    def recommend(self, observed_max_kmh: float, track_max_kmh: float) -> str:
        """
        Compare observed top speed to theoretical and track maximum.
        Returns a human-readable recommendation string.
        """
        theoretical = self.top_speed_kmh()
        diff_pct = (observed_max_kmh - theoretical) / theoretical * 100

        lines = []
        lines.append(
            f"Theoretical top speed: {theoretical:.1f} km/h  |  "
            f"Observed: {observed_max_kmh:.1f} km/h"
        )

        if abs(diff_pct) > 10:
            if diff_pct < 0:
                lines.append(
                    f"Motor may be current-limited before reaching free-running RPM "
                    f"({abs(diff_pct):.0f}% below theoretical).  "
                    "Consider raising Max Current or lowering axle sprocket teeth."
                )
            else:
                lines.append(
                    f"Observed speed exceeds theoretical by {diff_pct:.0f}%.  "
                    "Check motor RPM spec or tire diameter input."
                )

        if track_max_kmh > 0:
            if observed_max_kmh < track_max_kmh * 0.90:
                shortage = track_max_kmh - observed_max_kmh
                # New ratio to achieve track_max_kmh
                target_ratio = self.ratio * (observed_max_kmh / track_max_kmh)
                new_motor = self.motor_sprocket_teeth
                new_axle = round(new_motor * target_ratio)
                lines.append(
                    f"Short {shortage:.1f} km/h of track maximum.  "
                    f"Suggested: {new_motor}T motor / {new_axle}T axle  "
                    f"(ratio {target_ratio:.2f}:1)"
                )
            elif observed_max_kmh > track_max_kmh * 1.05:
                lines.append(
                    "Top speed exceeds track maximum — consider shortening ratio "
                    "to gain more acceleration torque."
                )
            else:
                lines.append("Gear ratio looks well-matched to this track.")

        return "\n".join(lines)

    def to_json(self, filepath: str) -> None:
        with open(filepath, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def from_json(cls, filepath: str) -> "GearRatioConfig":
        with open(filepath, "r") as f:
            d = json.load(f)
        return cls(**d)
