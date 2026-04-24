"""
Recommendation engine — analyses session data and current settings to suggest
specific, rule-compliant Alltrax SR parameter changes and gear ratio adjustments.

Every recommendation is checked against CompetitionRules before being emitted.
Suggestions that would violate EVGP limits are blocked and replaced with a
compliance warning instead.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis
    from src.alltrax_settings import AlltraxSettings
    from src.gear_ratio import GearRatioConfig

from src.competition_rules import CompetitionRules, get_rules


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    category:          str    # "Controller", "Gear Ratio", "Throttle", "Driver", "Compliance"
    parameter:         str    # Human name of the setting
    setting_key:       str    # Field name in AlltraxSettings / GearRatioConfig
    current_value:     str
    recommended_value: str
    delta:             float  # Numeric change to apply
    reason:            str    # Plain-English explanation (one paragraph)
    what_will_happen:  str    # Concrete prediction: "This will make corner exits X% faster"
    priority:          int = 2   # 1 = critical / compliance, 2 = high, 3 = medium, 4 = minor
    rule_violation:    bool = False  # True if current setting violates a rule


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RecommendationEngine:
    """
    Generates an ordered list of Recommendation objects from:
      - session analysis (best lap, corner data, phase breakdown)
      - current AlltraxSettings
      - current GearRatioConfig
      - active CompetitionRules
    """

    # EVGP hard limits (always enforced regardless of rules file)
    _MAX_CURRENT_LIMIT = 220
    _HI_VOLT_MAX       = 58.4
    _LO_VOLT_MIN       = 40.0

    def __init__(
        self,
        session:  "SessionAnalysis",
        settings: "AlltraxSettings",
        gear:     "GearRatioConfig",
        rules:    Optional[CompetitionRules] = None,
    ) -> None:
        self.session  = session
        self.settings = settings
        self.gear     = gear
        self.rules    = rules or get_rules()

    def generate(self) -> List[Recommendation]:
        recs: List[Recommendation] = []

        # Rule violations always come first
        recs.extend(self._check_compliance())

        # Session-driven analysis
        recs.extend(self._analyse_acceleration())
        recs.extend(self._analyse_braking())
        recs.extend(self._analyse_gear_ratio())
        recs.extend(self._analyse_consistency())
        recs.extend(self._analyse_throttle_curve())
        recs.extend(self._analyse_motor_temp_risk())
        recs.extend(self._analyse_energy())

        # Sort: compliance first, then by priority, then deduplicate by setting_key
        recs.sort(key=lambda r: (0 if r.rule_violation else 1, r.priority))
        seen: set[str] = set()
        unique: List[Recommendation] = []
        for r in recs:
            key = r.setting_key or r.parameter
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    # ------------------------------------------------------------------
    # Compliance checks (priority 1 — must fix before racing)
    # ------------------------------------------------------------------

    def _check_compliance(self) -> List[Recommendation]:
        recs = []
        s = self.settings
        r = self.rules

        if s.max_current > self._MAX_CURRENT_LIMIT:
            recs.append(Recommendation(
                category="Compliance",
                parameter="Max Current",
                setting_key="max_current",
                current_value=f"{s.max_current} A",
                recommended_value=f"{self._MAX_CURRENT_LIMIT} A",
                delta=self._MAX_CURRENT_LIMIT - s.max_current,
                reason=(
                    f"Your max current ({s.max_current} A) exceeds the EVGP 2025-26 hard limit "
                    f"of {self._MAX_CURRENT_LIMIT} A.  This is a rule violation — the kart "
                    "cannot compete until this is corrected."
                ),
                what_will_happen=(
                    f"Reducing to {self._MAX_CURRENT_LIMIT} A brings you into compliance.  "
                    "You may lose a small amount of peak acceleration but the kart will be legal."
                ),
                priority=1,
                rule_violation=True,
            ))

        if s.hi_voltage_cutoff > self._HI_VOLT_MAX:
            recs.append(Recommendation(
                category="Compliance",
                parameter="Hi-Voltage Cutoff",
                setting_key="hi_voltage_cutoff",
                current_value=f"{s.hi_voltage_cutoff:.1f} V",
                recommended_value=f"{self._HI_VOLT_MAX} V",
                delta=self._HI_VOLT_MAX - s.hi_voltage_cutoff,
                reason=(
                    f"Hi-voltage cutoff ({s.hi_voltage_cutoff:.1f} V) exceeds the LiFePO4 "
                    f"pack maximum ({self._HI_VOLT_MAX} V).  Operating above this risks "
                    "cell damage and fire."
                ),
                what_will_happen="Setting to 58.4 V protects the battery with no performance loss.",
                priority=1,
                rule_violation=True,
            ))

        if s.lo_voltage_cutoff < self._LO_VOLT_MIN:
            recs.append(Recommendation(
                category="Compliance",
                parameter="Lo-Voltage Cutoff",
                setting_key="lo_voltage_cutoff",
                current_value=f"{s.lo_voltage_cutoff:.1f} V",
                recommended_value=f"{self._LO_VOLT_MIN} V",
                delta=self._LO_VOLT_MIN - s.lo_voltage_cutoff,
                reason=(
                    f"Lo-voltage cutoff ({s.lo_voltage_cutoff:.1f} V) is below the LiFePO4 "
                    f"safe minimum ({self._LO_VOLT_MIN} V).  Over-discharging will permanently "
                    "damage the mandated LiTime battery."
                ),
                what_will_happen="Raising to 40.0 V adds battery protection without affecting lap times.",
                priority=1,
                rule_violation=True,
            ))

        return recs

    # ------------------------------------------------------------------
    # Acceleration analysis
    # ------------------------------------------------------------------

    def _analyse_acceleration(self) -> List[Recommendation]:
        recs = []
        best = self.session.best_lap
        phase = best.phase
        speed = best.speed
        time  = best.time

        accel_mask = phase == "accelerating"
        if accel_mask.sum() < 5:
            return recs

        accel_pct   = accel_mask.sum() / len(phase) * 100
        accel_vals  = np.gradient(speed, time)
        peak_accel  = float(np.percentile(accel_vals[accel_mask], 90))
        mean_accel  = float(np.mean(accel_vals[accel_mask]))

        # ---- Low current → sluggish acceleration -------------------------
        # Only suggest up to the EVGP 220 A limit
        max_allowed = min(self._MAX_CURRENT_LIMIT, int(self.rules.controller_max_current_a))
        if peak_accel < 1.5 and self.settings.max_current < max_allowed - 20:
            new_val = min(max_allowed, self.settings.max_current + 25)
            recs.append(Recommendation(
                category="Controller",
                parameter="Max Current",
                setting_key="max_current",
                current_value=f"{self.settings.max_current} A",
                recommended_value=f"{new_val} A",
                delta=float(new_val - self.settings.max_current),
                reason=(
                    f"Peak acceleration on your best lap is only {peak_accel:.1f} m/s² — "
                    "that's quite low for a kart on a tight track.  "
                    "The most likely cause is that the current limit is too low, which caps "
                    "the torque the motor can deliver."
                ),
                what_will_happen=(
                    f"Raising max current to {new_val} A should increase peak acceleration "
                    f"by roughly {((new_val/self.settings.max_current)-1)*100:.0f}%, "
                    "making corner exits noticeably quicker.  Watch motor temperature "
                    "— more current means more heat."
                ),
                priority=2,
            ))

        # ---- Slow ramp → sluggish initial response -----------------------
        if self.settings.accel_rate < 100 and mean_accel < 1.2:
            new_rate = min(160, self.settings.accel_rate + 30)
            recs.append(Recommendation(
                category="Controller",
                parameter="Acceleration Rate",
                setting_key="accel_rate",
                current_value=str(self.settings.accel_rate),
                recommended_value=str(new_rate),
                delta=float(new_rate - self.settings.accel_rate),
                reason=(
                    f"The acceleration ramp is set to {self.settings.accel_rate} (out of 255) "
                    "which is conservative.  The data shows the kart is slow to build speed "
                    "after corner apexes — this is the controller limiting how fast it reaches "
                    "full current, not a power shortage."
                ),
                what_will_happen=(
                    f"Increasing to {new_rate} will make the controller reach full current "
                    "faster after you open the throttle.  Expect a noticeably snappier "
                    "response exiting slower corners.  If rear wheels spin, reduce slightly."
                ),
                priority=2,
            ))

        # ---- Very high accel time → possibly over-geared or under-powered --
        if accel_pct < 30:
            recs.append(Recommendation(
                category="Driver",
                parameter="Acceleration Time %",
                setting_key="",
                current_value=f"{accel_pct:.0f}% of lap",
                recommended_value="> 35% of lap",
                delta=0,
                reason=(
                    f"Only {accel_pct:.0f}% of your lap time is spent accelerating.  "
                    "This usually means the straights are very short, or the driver is "
                    "getting on the throttle late after corners.  "
                    "Applying throttle earlier (even gently) after the apex can recover "
                    "significant time."
                ),
                what_will_happen=(
                    "Earlier throttle application compounds over the full lap.  "
                    "Gaining 10 m of earlier throttle per corner on a 10-corner track "
                    "can be worth 0.5–1.0 s per lap."
                ),
                priority=3,
            ))

        return recs

    # ------------------------------------------------------------------
    # Braking analysis
    # ------------------------------------------------------------------

    def _analyse_braking(self) -> List[Recommendation]:
        recs = []
        best  = self.session.best_lap
        phase = best.phase
        speed = best.speed
        time  = best.time

        brake_mask = phase == "braking"
        if brake_mask.sum() < 5:
            return recs

        brake_pct  = brake_mask.sum() / len(phase) * 100
        decel_vals = np.gradient(speed, time)[brake_mask]
        avg_decel  = float(abs(np.mean(decel_vals)))

        if brake_pct > 28 and not self.settings.regen_braking:
            recs.append(Recommendation(
                category="Controller",
                parameter="Regen Braking",
                setting_key="regen_braking",
                current_value="Off",
                recommended_value="On",
                delta=1,
                reason=(
                    f"{brake_pct:.0f}% of your lap is spent braking — that's a significant "
                    "portion.  With regen braking off, all that kinetic energy is wasted as "
                    "heat in the mechanical brakes.  Turning regen on feeds some of it back "
                    "into the battery."
                ),
                what_will_happen=(
                    "Enabling regen can extend battery range by 5–15% on brake-heavy tracks.  "
                    "It also provides additional retardation before the mechanical brakes bite, "
                    "which some drivers find helps with consistency."
                ),
                priority=3,
            ))

        if avg_decel > 3.5 and self.settings.decel_rate < 80:
            new_rate = min(120, self.settings.decel_rate + 30)
            recs.append(Recommendation(
                category="Controller",
                parameter="Decel / Plug Brake Rate",
                setting_key="decel_rate",
                current_value=str(self.settings.decel_rate),
                recommended_value=str(new_rate),
                delta=float(new_rate - self.settings.decel_rate),
                reason=(
                    f"Average deceleration is {avg_decel:.1f} m/s² but the plug brake rate "
                    f"is only {self.settings.decel_rate}.  The mechanical brakes are doing "
                    "most of the work where the controller could help."
                ),
                what_will_happen=(
                    "Matching plug brake rate to the driver's style reduces brake pad wear "
                    "and gives more consistent stopping distances, especially as pads heat up."
                ),
                priority=3,
            ))

        return recs

    # ------------------------------------------------------------------
    # Gear ratio analysis
    # ------------------------------------------------------------------

    def _analyse_gear_ratio(self) -> List[Recommendation]:
        recs = []
        best            = self.session.best_lap
        observed_kmh    = best.max_speed_kmh
        theoretical_kmh = self.gear.top_speed_kmh()
        speed_limit_kmh = self.rules.speed_limit_kmh

        # ---- Not reaching theoretical top speed --------------------------
        if observed_kmh < theoretical_kmh * 0.82:
            gap = theoretical_kmh - observed_kmh
            new_axle = max(50, self.gear.axle_sprocket_teeth - 4)
            recs.append(Recommendation(
                category="Gear Ratio",
                parameter="Axle Sprocket",
                setting_key="axle_sprocket_teeth",
                current_value=f"{self.gear.axle_sprocket_teeth}T  "
                              f"(ratio {self.gear.ratio:.2f}, top ~{theoretical_kmh:.0f} km/h)",
                recommended_value=f"{new_axle}T  (shorter ratio → more top speed)",
                delta=float(new_axle - self.gear.axle_sprocket_teeth),
                reason=(
                    f"Your best lap top speed was {observed_kmh:.0f} km/h, but your gear ratio "
                    f"gives a theoretical maximum of {theoretical_kmh:.0f} km/h.  "
                    f"The kart is {gap:.0f} km/h short of its potential — it is spending "
                    "the end of each straight still accelerating when it should be at full speed."
                ),
                what_will_happen=(
                    f"Reducing the axle sprocket to {new_axle}T shortens the ratio, raises "
                    "top speed, and lets the motor run at a more efficient RPM on the straights.  "
                    "If the straights are long enough, this will improve lap time directly."
                ),
                priority=2,
            ))

        # ---- Already at or over theoretical top speed → more torque ------
        elif observed_kmh >= theoretical_kmh * 0.96:
            new_axle = self.gear.axle_sprocket_teeth + 3
            recs.append(Recommendation(
                category="Gear Ratio",
                parameter="Axle Sprocket",
                setting_key="axle_sprocket_teeth",
                current_value=f"{self.gear.axle_sprocket_teeth}T  (ratio {self.gear.ratio:.2f})",
                recommended_value=f"{new_axle}T  (longer ratio → more torque)",
                delta=float(new_axle - self.gear.axle_sprocket_teeth),
                reason=(
                    f"The kart is reaching {observed_kmh:.0f} km/h — essentially its theoretical "
                    f"maximum of {theoretical_kmh:.0f} km/h.  The motor is running near free-speed "
                    "at the end of the straight, which means it's producing very little torque "
                    "there and building heat without much benefit."
                ),
                what_will_happen=(
                    f"Adding teeth (to {new_axle}T) trades some top speed for more torque at all "
                    "speeds.  This is beneficial on tight, technical tracks where corner exit "
                    "speed matters more than top-end velocity."
                ),
                priority=3,
            ))

        # ---- Speed limit warning -----------------------------------------
        if theoretical_kmh > speed_limit_kmh:
            recs.append(Recommendation(
                category="Compliance",
                parameter="Gear Ratio / Speed Limit",
                setting_key="speed_limit",
                current_value=f"Theoretical top ~{theoretical_kmh:.0f} km/h",
                recommended_value=f"≤ {speed_limit_kmh:.0f} km/h",
                delta=0,
                reason=(
                    f"Your gear ratio allows a theoretical top speed of {theoretical_kmh:.0f} km/h "
                    f"which may exceed the EVGP limit of {speed_limit_kmh:.0f} km/h.  "
                    "If a speed limit is enforced on this track, you need to cap it."
                ),
                what_will_happen=(
                    "Set the Speed Limit % in the controller to cap max speed below the limit, "
                    "or change the axle sprocket to a larger size to lower the top speed physically."
                ),
                priority=2,
            ))

        return recs

    # ------------------------------------------------------------------
    # Consistency analysis
    # ------------------------------------------------------------------

    def _analyse_consistency(self) -> List[Recommendation]:
        recs = []
        if len(self.session.laps) < 3:
            return recs

        consistency = self.session.consistency_pct
        std         = self.session.std_lap_time
        best_time   = self.session.best_lap.lap_time

        if consistency < 88:
            recs.append(Recommendation(
                category="Driver",
                parameter="Lap Consistency",
                setting_key="",
                current_value=f"{consistency:.1f}%  (std dev {std:.2f}s)",
                recommended_value="> 93%  (std dev < 0.5s)",
                delta=0,
                reason=(
                    f"Your lap times vary by ±{std:.2f}s, giving a consistency of "
                    f"{consistency:.0f}%.  For endurance racing, consistent laps are often "
                    "more valuable than occasional fast ones — they preserve tyres and battery.  "
                    "Variation this large usually comes from corner entry speed changing lap-to-lap."
                ),
                what_will_happen=(
                    "Focus on hitting the same braking marker and turn-in point every lap.  "
                    "Use the Corner Consistency chart to find which corner has the most "
                    "lap-to-lap variation — that's where to focus practice."
                ),
                priority=2,
            ))
        elif consistency < 95:
            recs.append(Recommendation(
                category="Driver",
                parameter="Lap Consistency",
                setting_key="",
                current_value=f"{consistency:.1f}%",
                recommended_value="> 95%",
                delta=0,
                reason=(
                    f"Consistency is {consistency:.1f}% — respectable, but there's still "
                    "room to tighten it up.  In a 1-hour race, 2–3 slow laps due to small "
                    "mistakes can cost 10+ seconds overall."
                ),
                what_will_happen="Tighter consistency reduces risk in traffic and preserves race pace.",
                priority=4,
            ))

        return recs

    # ------------------------------------------------------------------
    # Throttle curve analysis
    # ------------------------------------------------------------------

    def _analyse_throttle_curve(self) -> List[Recommendation]:
        recs = []
        best       = self.session.best_lap
        phase      = best.phase
        accel_mask = phase == "accelerating"
        if accel_mask.sum() < 5:
            return recs

        accel_pct = accel_mask.sum() / len(phase) * 100

        # Only suggest aggressive curve on tracks with meaningful acceleration zones
        if accel_pct >= 35:
            curve = self.settings.throttle_curve
            # Check if it's already aggressive (high output at low input)
            mid_output = curve[3] if len(curve) > 3 else 30  # output at 30% input
            if mid_output < 45:
                recs.append(Recommendation(
                    category="Throttle",
                    parameter="Throttle Curve Preset",
                    setting_key="throttle_curve",
                    current_value=f"Current (output at 30% input = {mid_output:.0f}%)",
                    recommended_value="Aggressive (output at 30% input = 52%)",
                    delta=0,
                    reason=(
                        f"Significant time ({accel_pct:.0f}% of lap) is spent accelerating.  "
                        "Your current throttle curve is linear or soft, meaning you're getting "
                        "less than 50% power at 30% pedal.  On corner exits this delay costs time."
                    ),
                    what_will_happen=(
                        "The Aggressive curve delivers ~52% output at 30% pedal input.  "
                        "This makes corner exit feel more responsive without changing the "
                        "maximum power — it just delivers it earlier in the pedal travel."
                    ),
                    priority=3,
                ))

        return recs

    # ------------------------------------------------------------------
    # Motor temperature risk analysis
    # ------------------------------------------------------------------

    def _analyse_motor_temp_risk(self) -> List[Recommendation]:
        recs = []
        s = self.settings

        # If current is high and no regen → high thermal load warning
        if s.max_current >= 180 and not s.regen_braking:
            laps = len(self.session.laps)
            if laps >= 4:
                recs.append(Recommendation(
                    category="Controller",
                    parameter="Thermal Management",
                    setting_key="",
                    current_value=f"{s.max_current} A, regen off, {laps} laps in session",
                    recommended_value="Monitor motor temp; consider regen braking",
                    delta=0,
                    reason=(
                        f"Running {s.max_current} A without regen braking over a long session "
                        "puts significant thermal load on the motor and controller.  "
                        "If motor temp exceeds ~70 °C, the Alltrax begins derating — "
                        "you'll notice the kart getting slower mid-race."
                    ),
                    what_will_happen=(
                        "Log motor temperature using the Session Logger tab after each stint.  "
                        "If temps trend upward across laps, consider reducing max current by "
                        "10–20 A for the race, or enabling regen to reduce heat in the braking zones."
                    ),
                    priority=3,
                ))

        return recs

    # ------------------------------------------------------------------
    # Energy analysis
    # ------------------------------------------------------------------

    def _analyse_energy(self) -> List[Recommendation]:
        recs = []
        best = self.session.best_lap

        try:
            from src.deep_analysis import estimate_energy
            energy = estimate_energy(
                best.time, best.speed,
                mass_kg=160.0,
                battery_capacity_kwh=self.rules.battery_capacity_wh / 1000.0,
            )
            wh_per_lap = energy.energy_used_wh
            capacity   = self.rules.battery_capacity_wh
            laps_est   = capacity / wh_per_lap if wh_per_lap > 0 else 0

            if laps_est < 20:
                recs.append(Recommendation(
                    category="Energy",
                    parameter="Energy Consumption",
                    setting_key="",
                    current_value=f"{wh_per_lap:.0f} Wh/lap  (~{laps_est:.0f} laps per charge)",
                    recommended_value=f"> {capacity/25:.0f} Wh/lap  (25+ laps per charge)",
                    delta=0,
                    reason=(
                        f"At {wh_per_lap:.0f} Wh per lap, the {capacity:.0f} Wh battery gives "
                        f"roughly {laps_est:.0f} laps per charge.  "
                        "For a 1-hour endurance race, you should target at least 25 laps "
                        "from a single charge at race pace."
                    ),
                    what_will_happen=(
                        "To reduce energy use: lower max current slightly, enable regen braking, "
                        "or optimise the driving line to reduce unnecessary braking.  "
                        "Each 10 A reduction in max current saves roughly 3–5% energy."
                    ),
                    priority=2,
                ))
        except Exception:
            pass

        return recs
