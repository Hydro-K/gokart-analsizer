"""
Recommendation engine: analyses session data and current settings to suggest
Alltrax SR-72400 parameter changes and gear ratio adjustments.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis
    from src.alltrax_settings import AlltraxSettings
    from src.gear_ratio import GearRatioConfig


@dataclass
class Recommendation:
    category: str           # "Alltrax", "Gear Ratio", "Throttle Curve", "Driver"
    parameter: str          # human name of the setting
    setting_key: str        # key in AlltraxSettings / GearRatioConfig
    current_value: str
    recommended_value: str
    delta: float            # +/- change (for spinbox apply)
    reason: str
    priority: int = 2       # 1=high, 2=medium, 3=low


class RecommendationEngine:
    def __init__(
        self,
        session: "SessionAnalysis",
        settings: "AlltraxSettings",
        gear: "GearRatioConfig",
    ) -> None:
        self.session = session
        self.settings = settings
        self.gear = gear

    def generate(self) -> List[Recommendation]:
        recs: List[Recommendation] = []
        best = self.session.best_lap
        speed_ms = best.speed
        time = best.time
        phase = best.phase

        # ---------- Acceleration analysis ----------------------------------
        accel_mask = phase == "accelerating"
        if accel_mask.sum() > 5:
            accel_pct = accel_mask.sum() / len(phase) * 100
            accel_smoothed = np.gradient(speed_ms, time)
            accel_vals = accel_smoothed[accel_mask]
            peak_accel = np.percentile(accel_vals, 90)  # m/s²

            # If peak acceleration < 2 m/s² and current < 350A → raise current
            if peak_accel < 2.0 and self.settings.max_current < 370:
                new_current = min(400, self.settings.max_current + 30)
                recs.append(Recommendation(
                    category="Alltrax",
                    parameter="Max Current",
                    setting_key="max_current",
                    current_value=f"{self.settings.max_current} A",
                    recommended_value=f"{new_current} A",
                    delta=new_current - self.settings.max_current,
                    reason=(
                        f"Peak acceleration is only {peak_accel:.1f} m/s².  "
                        "Raising max current will increase torque and improve out-of-corner acceleration."
                    ),
                    priority=1,
                ))

            # Accel rate: if phase shows slow ramp early, increase accel_rate
            if self.settings.accel_rate < 120:
                recs.append(Recommendation(
                    category="Alltrax",
                    parameter="Acceleration Rate",
                    setting_key="accel_rate",
                    current_value=str(self.settings.accel_rate),
                    recommended_value=str(min(255, self.settings.accel_rate + 20)),
                    delta=20,
                    reason=(
                        "Current acceleration ramp is conservative.  "
                        "Increasing accel rate will reduce time-to-full-current on corner exits."
                    ),
                    priority=2,
                ))

        # ---------- Braking analysis ---------------------------------------
        brake_mask = phase == "braking"
        if brake_mask.sum() > 5:
            brake_pct = brake_mask.sum() / len(phase) * 100
            accel_vals = np.gradient(speed_ms, time)
            brake_vals = accel_vals[brake_mask]
            avg_decel = abs(np.mean(brake_vals))

            # If lots of braking time, suggest plug/regen braking
            if brake_pct > 25 and not self.settings.regen_braking:
                recs.append(Recommendation(
                    category="Alltrax",
                    parameter="Regen Braking",
                    setting_key="regen_braking",
                    current_value="Off",
                    recommended_value="On",
                    delta=1,
                    reason=(
                        f"{brake_pct:.0f}% of lap time spent braking.  "
                        "Enabling regen braking will recover energy and shorten stopping distance."
                    ),
                    priority=2,
                ))

            if avg_decel > 3.0 and self.settings.decel_rate < 100:
                new_decel = min(255, self.settings.decel_rate + 25)
                recs.append(Recommendation(
                    category="Alltrax",
                    parameter="Decel/Plug Brake Rate",
                    setting_key="decel_rate",
                    current_value=str(self.settings.decel_rate),
                    recommended_value=str(new_decel),
                    delta=25,
                    reason=(
                        f"High deceleration detected ({avg_decel:.1f} m/s²).  "
                        "Matching plug brake rate to driving style will improve consistency."
                    ),
                    priority=3,
                ))

        # ---------- Throttle curve -----------------------------------------
        # If accel rate low and lots of time near low throttle, suggest aggressive curve
        if accel_pct < 40 if accel_mask.sum() > 0 else True:
            recs.append(Recommendation(
                category="Throttle Curve",
                parameter="Throttle Curve Preset",
                setting_key="throttle_curve",
                current_value="Current curve",
                recommended_value="Aggressive",
                delta=0,
                reason=(
                    "Less than 40% of lap time is spent accelerating.  "
                    "An Aggressive throttle curve gives more response at low pedal inputs, "
                    "reducing the time to build current after corner apex."
                ),
                priority=3,
            ))

        # ---------- Gear ratio analysis ------------------------------------
        observed_max_kmh = best.max_speed_kmh
        theoretical_kmh = self.gear.top_speed_kmh()

        if observed_max_kmh < theoretical_kmh * 0.85:
            # Not reaching theoretical top speed — likely current-limited or wrong ratio
            recs.append(Recommendation(
                category="Gear Ratio",
                parameter="Axle Sprocket",
                setting_key="axle_sprocket_teeth",
                current_value=f"{self.gear.axle_sprocket_teeth}T",
                recommended_value=f"{max(50, self.gear.axle_sprocket_teeth - 4)}T",
                delta=-4,
                reason=(
                    f"Top speed is {observed_max_kmh:.1f} km/h vs theoretical {theoretical_kmh:.1f} km/h.  "
                    "Shortening the ratio (fewer axle teeth) will increase top speed "
                    "and may reduce motor temperature."
                ),
                priority=2,
            ))
        elif observed_max_kmh > theoretical_kmh * 0.97:
            # Reaching or exceeding theoretical top — consider lengthening for torque
            recs.append(Recommendation(
                category="Gear Ratio",
                parameter="Axle Sprocket",
                setting_key="axle_sprocket_teeth",
                current_value=f"{self.gear.axle_sprocket_teeth}T",
                recommended_value=f"{self.gear.axle_sprocket_teeth + 4}T",
                delta=4,
                reason=(
                    f"Motor reaching free-running RPM at {observed_max_kmh:.1f} km/h.  "
                    "Lengthening the ratio (more axle teeth) trades top speed for "
                    "more torque, improving corner exit acceleration on tight tracks."
                ),
                priority=3,
            ))

        # ---------- Consistency -------------------------------------------
        if self.session.consistency_pct < 90 and len(self.session.laps) >= 3:
            recs.append(Recommendation(
                category="Driver",
                parameter="Lap Consistency",
                setting_key="",
                current_value=f"{self.session.consistency_pct:.1f}%",
                recommended_value=">95%",
                delta=0,
                reason=(
                    f"Lap time standard deviation is {self.session.std_lap_time:.2f}s.  "
                    "Focus on consistent corner entry speeds — the data shows variability "
                    "in corner apex speeds across laps."
                ),
                priority=2,
            ))

        # Sort by priority
        recs.sort(key=lambda r: r.priority)
        return recs
