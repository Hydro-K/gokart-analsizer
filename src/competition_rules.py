"""
Purdue EV Grand Prix High School 2025-26 — Competition Rule Definitions &
Compliance Checker.

Key specs sourced from publicly available competition documentation:
  • Battery:    LiTime 48V 60 Ah LiFePO4, 3072 Wh, 120 A BMS — 51.2 V nominal
  • Controller: Alltrax SPM or SR 48300 / 48400 / 48500 / 48600 ONLY
  • Max current: 220 A (motor AND battery limits)
  • Tyres:      Hoosier R60B — front 4.5/10.0/5, rear 7.1/11.0/5
  • Chassis:    Top-Kart mandated chassis

All limits are stored in ~/.evkart_rules.json and can be edited inside the
app (Rules tab → Edit Limits) without code changes.

Fields marked ⚠ VERIFY must be confirmed against the official PDF — the
primary source is:
  https://engineering.purdue.edu/evGrandPrix/highschool/Documents/
  evGrandPrix-High-School-2025-26-Rules.pdf
"""

from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.alltrax_settings import AlltraxSettings
    from src.gear_ratio import GearRatioConfig

_RULES_FILE = Path.home() / ".evkart_rules.json"


# ---------------------------------------------------------------------------
# Rule limit definitions
# ---------------------------------------------------------------------------

@dataclass
class CompetitionRules:
    """
    Every numeric limit that can be checked programmatically.
    Edit values in the Rules tab — saved to ~/.evkart_rules.json.
    """

    # ---- Battery / Electrical (LiTime 48V 60Ah LiFePO4) -------------------
    battery_voltage_nominal_v: float = 51.2
    """Nominal pack voltage — 16S LiFePO4 × 3.2 V/cell = 51.2 V."""

    battery_voltage_max_v: float = 58.4
    """Max fully-charged voltage — 16S × 3.65 V/cell = 58.4 V."""

    battery_voltage_min_v: float = 40.0
    """Minimum discharge cutoff — 16S × 2.5 V/cell = 40.0 V."""

    battery_capacity_wh: float = 3072.0
    """Mandatory pack capacity in Wh (LiTime 48V 60Ah = 3072 Wh)."""

    battery_capacity_ah: float = 60.0
    """Mandatory pack capacity in Ah."""

    battery_bms_max_current_a: float = 120.0
    """BMS continuous discharge rating (A) — do not sustain above this."""

    # ---- Controller --------------------------------------------------------
    # Mandated models: Alltrax SPM or SR 48300 / 48400 / 48500 / 48600 ONLY.
    # The model number encodes voltage (48V) and peak current (300–600 A).
    controller_max_current_a: float = 220.0
    """
    Competition-mandated maximum controller current setting (A).
    Both motor current limit AND battery current limit must be ≤ 220 A.
    Source: EVGP 2025-26 rules — confirmed from competition documentation.
    """

    controller_allowed_models: str = "Alltrax SPM/SR 48300, 48400, 48500, 48600"
    """Allowed controller models (informational — cannot be checked in software)."""

    # ---- Speed / Performance -----------------------------------------------
    speed_limit_kmh: float = 80.0
    """Maximum allowable top speed (km/h ≈ 50 mph). ⚠ VERIFY in rulebook."""

    # ---- Tyres (Hoosier R60B — mandated compound) --------------------------
    tyre_compound: str = "Hoosier R60B"
    """Mandated tyre compound. ⚠ No other compounds are allowed."""

    tyre_front_size: str = "4.5/10.0/5"
    """Mandated front tyre size."""

    tyre_rear_size: str = "7.1/11.0/5"
    """Mandated rear tyre size."""

    tyre_pressure_min_psi: float = 10.0
    """Minimum cold tyre pressure (PSI). ⚠ VERIFY exact limit in rulebook."""

    tyre_pressure_max_psi: float = 22.0
    """Maximum cold tyre pressure (PSI). ⚠ VERIFY exact limit in rulebook."""

    # ---- Chassis -----------------------------------------------------------
    chassis_required: str = "Top-Kart (mandated model)"
    """Required chassis — only Top-Kart mandated models are allowed."""

    # ---- Vehicle Weight ----------------------------------------------------
    combined_min_weight_kg: float = 181.4
    """Minimum kart + driver weight (kg ≈ 400 lb). ⚠ VERIFY in rulebook."""

    # ---- Controller voltage cutoffs ----------------------------------------
    controller_lo_cutoff_min_v: float = 40.0
    """Controller low-voltage cutoff must be ≥ this (protects battery)."""

    controller_hi_cutoff_max_v: float = 58.4
    """Controller high-voltage cutoff must be ≤ this (battery safety)."""

    # ---- Metadata ----------------------------------------------------------
    rulebook_version: str = "2025-26"
    notes: str = (
        "Max current 220 A confirmed from competition documentation. "
        "Speed limit, weight, and tyre pressures marked ⚠ VERIFY. "
        "Always cross-check against the official PDF before race day."
    )

    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CompetitionRules":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

    def save(self) -> None:
        _RULES_FILE.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls) -> "CompetitionRules":
        if _RULES_FILE.exists():
            try:
                return cls.from_dict(json.loads(_RULES_FILE.read_text()))
            except Exception:
                pass
        return cls()


# ---------------------------------------------------------------------------
# Compliance result types
# ---------------------------------------------------------------------------

@dataclass
class ComplianceItem:
    rule_name: str      # Short label shown in the table
    rule_section: str   # Category / section reference
    current_value: str  # What is currently set
    limit_value: str    # The rule limit
    status: str         # "PASS" | "FAIL" | "WARN" | "VERIFY"
    message: str        # Plain-English explanation
    actionable: str     # What to do about it


@dataclass
class ComplianceReport:
    items: List[ComplianceItem] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(i.status in ("PASS", "VERIFY") for i in self.items)

    @property
    def fail_count(self) -> int:
        return sum(1 for i in self.items if i.status == "FAIL")

    @property
    def warn_count(self) -> int:
        return sum(1 for i in self.items if i.status == "WARN")

    @property
    def verify_count(self) -> int:
        return sum(1 for i in self.items if i.status == "VERIFY")

    def summary_line(self) -> str:
        if self.fail_count:
            return f"⛔  {self.fail_count} RULE VIOLATION(S) — kart is NOT compliant"
        if self.warn_count:
            return f"⚠  {self.warn_count} WARNING(S) — check before race day"
        if self.verify_count:
            return f"ℹ  {self.verify_count} item(s) need manual verification"
        return "✅  All checked parameters appear compliant"


# ---------------------------------------------------------------------------
# Compliance checker
# ---------------------------------------------------------------------------

class ComplianceChecker:
    """
    Checks AlltraxSettings and GearRatioConfig against CompetitionRules.
    Returns a ComplianceReport with one ComplianceItem per rule.
    """

    def __init__(self, rules: CompetitionRules) -> None:
        self.rules = rules

    def check(
        self,
        settings: "AlltraxSettings",
        gear: "GearRatioConfig",
        kart_mass_kg: float = 90.0,
        driver_mass_kg: float = 68.0,
    ) -> ComplianceReport:
        r = self.rules
        report = ComplianceReport()
        add = report.items.append

        # ---- 1. Max current (CRITICAL — 220 A limit) ----------------------
        if settings.max_current > r.controller_max_current_a:
            add(ComplianceItem(
                rule_name="Max Controller Current",
                rule_section="Electrical § Controller",
                current_value=f"{settings.max_current} A",
                limit_value=f"≤ {r.controller_max_current_a:.0f} A",
                status="FAIL",
                message=(
                    f"⛔ RULE VIOLATION: Your max current is set to {settings.max_current} A, "
                    f"but the EVGP rules cap both motor AND battery current at "
                    f"{r.controller_max_current_a:.0f} A.  The kart cannot compete until "
                    "this is corrected."
                ),
                actionable=(
                    f"Open Settings tab → reduce Max Current to "
                    f"≤ {r.controller_max_current_a:.0f} A immediately."
                ),
            ))
        elif settings.max_current > r.controller_max_current_a * 0.95:
            add(ComplianceItem(
                rule_name="Max Controller Current",
                rule_section="Electrical § Controller",
                current_value=f"{settings.max_current} A",
                limit_value=f"≤ {r.controller_max_current_a:.0f} A",
                status="WARN",
                message=(
                    f"Current is {settings.max_current} A — within 5% of the "
                    f"{r.controller_max_current_a:.0f} A limit.  One programming error "
                    "could push you over the limit."
                ),
                actionable="Consider leaving a small margin (≤ 210 A) for safety.",
            ))
        else:
            add(ComplianceItem(
                rule_name="Max Controller Current",
                rule_section="Electrical § Controller",
                current_value=f"{settings.max_current} A",
                limit_value=f"≤ {r.controller_max_current_a:.0f} A",
                status="PASS",
                message=f"Current setting ({settings.max_current} A) is within the allowed {r.controller_max_current_a:.0f} A limit.",
                actionable="No action needed.",
            ))

        # ---- 2. Hi-voltage cutoff -----------------------------------------
        if settings.hi_voltage_cutoff > r.controller_hi_cutoff_max_v:
            add(ComplianceItem(
                rule_name="Battery Hi-Voltage Cutoff",
                rule_section="Electrical § Battery",
                current_value=f"{settings.hi_voltage_cutoff:.1f} V",
                limit_value=f"≤ {r.controller_hi_cutoff_max_v:.1f} V",
                status="FAIL",
                message=(
                    f"Hi-voltage cutoff ({settings.hi_voltage_cutoff:.1f} V) exceeds the "
                    f"LiFePO4 pack maximum ({r.controller_hi_cutoff_max_v:.1f} V).  "
                    "Over-charging LiFePO4 cells risks fire."
                ),
                actionable=f"Set hi_voltage_cutoff ≤ {r.controller_hi_cutoff_max_v:.1f} V.",
            ))
        else:
            add(ComplianceItem(
                rule_name="Battery Hi-Voltage Cutoff",
                rule_section="Electrical § Battery",
                current_value=f"{settings.hi_voltage_cutoff:.1f} V",
                limit_value=f"≤ {r.controller_hi_cutoff_max_v:.1f} V",
                status="PASS",
                message="Hi-voltage cutoff is safely set for the LiFePO4 pack.",
                actionable="No action needed.",
            ))

        # ---- 3. Lo-voltage cutoff -----------------------------------------
        if settings.lo_voltage_cutoff < r.controller_lo_cutoff_min_v:
            add(ComplianceItem(
                rule_name="Battery Lo-Voltage Cutoff",
                rule_section="Electrical § Battery",
                current_value=f"{settings.lo_voltage_cutoff:.1f} V",
                limit_value=f"≥ {r.controller_lo_cutoff_min_v:.1f} V",
                status="FAIL",
                message=(
                    f"Lo-voltage cutoff ({settings.lo_voltage_cutoff:.1f} V) is below the "
                    f"safe minimum ({r.controller_lo_cutoff_min_v:.1f} V).  "
                    "Over-discharging LiFePO4 causes permanent cell damage."
                ),
                actionable=f"Raise lo_voltage_cutoff to ≥ {r.controller_lo_cutoff_min_v:.1f} V.",
            ))
        else:
            add(ComplianceItem(
                rule_name="Battery Lo-Voltage Cutoff",
                rule_section="Electrical § Battery",
                current_value=f"{settings.lo_voltage_cutoff:.1f} V",
                limit_value=f"≥ {r.controller_lo_cutoff_min_v:.1f} V",
                status="PASS",
                message="Lo-voltage cutoff is safely above the minimum discharge limit.",
                actionable="No action needed.",
            ))

        # ---- 4. Estimated top speed ----------------------------------------
        estimated_top_kmh = gear.top_speed_kmh()
        speed_mph = estimated_top_kmh / 1.609
        limit_mph = r.speed_limit_kmh / 1.609
        if estimated_top_kmh > r.speed_limit_kmh:
            add(ComplianceItem(
                rule_name="Estimated Top Speed",
                rule_section="Performance § Speed ⚠ VERIFY",
                current_value=f"~{estimated_top_kmh:.1f} km/h  (~{speed_mph:.0f} mph)",
                limit_value=f"≤ {r.speed_limit_kmh:.0f} km/h  (≤ {limit_mph:.0f} mph)",
                status="WARN",
                message=(
                    f"Your gear ratio gives a theoretical top of ~{estimated_top_kmh:.1f} km/h, "
                    f"which may exceed the {r.speed_limit_kmh:.0f} km/h limit.  "
                    "Note: the controller's Speed Limit % can cap this without changing sprockets."
                ),
                actionable=(
                    "Either increase the axle sprocket teeth (larger number = lower top speed) "
                    f"or set Speed Limit % so that max speed stays ≤ {r.speed_limit_kmh:.0f} km/h."
                ),
            ))
        else:
            add(ComplianceItem(
                rule_name="Estimated Top Speed",
                rule_section="Performance § Speed ⚠ VERIFY",
                current_value=f"~{estimated_top_kmh:.1f} km/h  (~{speed_mph:.0f} mph)",
                limit_value=f"≤ {r.speed_limit_kmh:.0f} km/h  (≤ {limit_mph:.0f} mph)",
                status="PASS",
                message="Theoretical top speed is within the allowed limit.",
                actionable="Confirm with track data after loading a session.",
            ))

        # ---- 5. Combined weight -------------------------------------------
        combined_kg = kart_mass_kg + driver_mass_kg
        combined_lb = combined_kg * 2.205
        min_lb = r.combined_min_weight_kg * 2.205
        if combined_kg < r.combined_min_weight_kg:
            add(ComplianceItem(
                rule_name="Combined Weight (Kart + Driver)",
                rule_section="Vehicle § Weight ⚠ VERIFY",
                current_value=f"{combined_kg:.1f} kg  ({combined_lb:.0f} lb)",
                limit_value=f"≥ {r.combined_min_weight_kg:.0f} kg  ({min_lb:.0f} lb)",
                status="WARN",
                message=(
                    f"Estimated combined weight ({combined_kg:.1f} kg / {combined_lb:.0f} lb) "
                    f"is below the minimum ({r.combined_min_weight_kg:.0f} kg / {min_lb:.0f} lb).  "
                    "Ballast may be required."
                ),
                actionable="Add ballast and verify on official scales at scrutineering.",
            ))
        else:
            add(ComplianceItem(
                rule_name="Combined Weight (Kart + Driver)",
                rule_section="Vehicle § Weight ⚠ VERIFY",
                current_value=f"{combined_kg:.1f} kg  ({combined_lb:.0f} lb)",
                limit_value=f"≥ {r.combined_min_weight_kg:.0f} kg  ({min_lb:.0f} lb)",
                status="PASS",
                message="Estimated combined weight meets the minimum requirement.",
                actionable="Confirm on official scales at the event.",
            ))

        # ---- 6. Speed Limit % in controller ---------------------------------
        if settings.speed_limit < 100:
            add(ComplianceItem(
                rule_name="Controller Speed Limiter",
                rule_section="Electrical § Controller",
                current_value=f"{settings.speed_limit}% of max RPM",
                limit_value="Informational",
                status="PASS",
                message=(
                    f"Speed limiter is set to {settings.speed_limit}%.  "
                    "This is useful for wet conditions or when a track speed limit applies."
                ),
                actionable=(
                    "If you need full performance, raise to 100%.  "
                    "Leave lower if the track imposes a speed cap."
                ),
            ))

        # ---- 7. Controller model (informational) ---------------------------
        add(ComplianceItem(
            rule_name="Controller Model",
            rule_section="Electrical § Controller ⚠ VERIFY",
            current_value="Cannot detect from software",
            limit_value=r.controller_allowed_models,
            status="VERIFY",
            message=(
                "Only Alltrax SPM or SR 48300 / 48400 / 48500 / 48600 are allowed.  "
                "The app is configured for SR-72400 parameters — verify your physical "
                "controller matches an allowed model before tech inspection."
            ),
            actionable="Confirm controller model at scrutineering.",
        ))

        # ---- 8. Tyre compound (informational) -------------------------------
        add(ComplianceItem(
            rule_name="Tyre Compound",
            rule_section="Tyres ⚠ VERIFY",
            current_value="Cannot detect from software",
            limit_value=f"{r.tyre_compound} — front {r.tyre_front_size}, rear {r.tyre_rear_size}",
            status="VERIFY",
            message=(
                f"Mandatory tyre: {r.tyre_compound}.  "
                f"Front size: {r.tyre_front_size}  |  Rear size: {r.tyre_rear_size}.  "
                "No other compounds or sizes are permitted."
            ),
            actionable="Physically confirm correct Hoosier R60B tyres are mounted.",
        ))

        # ---- 9. Safety equipment (mandatory manual checks) -----------------
        for name, desc, action in [
            (
                "Kill Switch",
                "An externally accessible kill switch (reachable by marshals from outside the kart) "
                "is mandatory. It must be clearly labelled and tested before each session.",
                "Install, label, and test kill switch. Show marshals where it is.",
            ),
            (
                "Driver Safety Equipment",
                "Closed-face helmet with integral chin guard, gloves, and appropriate racing suit "
                "are required. Scrutineers check this at tech inspection.",
                "Ensure helmet, gloves, and suit are present and meet requirements.",
            ),
            (
                "Battery BMS",
                "The LiTime BMS (120 A) must be installed and functional. It protects the pack "
                "from over-voltage, under-voltage, and over-current events.",
                "Test BMS protection functions before race day.",
            ),
        ]:
            add(ComplianceItem(
                rule_name=name,
                rule_section="Safety ⚠ VERIFY",
                current_value="Cannot check in software",
                limit_value="Required — manual check only",
                status="VERIFY",
                message=desc,
                actionable=action,
            ))

        return report


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_active_rules: Optional[CompetitionRules] = None


def get_rules() -> CompetitionRules:
    global _active_rules
    if _active_rules is None:
        _active_rules = CompetitionRules.load()
    return _active_rules


def set_rules(rules: CompetitionRules) -> None:
    global _active_rules
    _active_rules = rules
    rules.save()
