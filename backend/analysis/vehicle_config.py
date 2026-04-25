"""
Vehicle and motor configuration model.
Stores kart-specific parameters used for energy, force, and performance calculations.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class VehicleConfig:
    # --- Identity --------------------------------------------------------
    name: str = "Purdue EV Kart"
    notes: str = ""

    # --- Mass ------------------------------------------------------------
    kart_mass_kg: float = 115.0     # bare kart without driver
    driver_mass_kg: float = 70.0    # driver + gear

    # --- Aerodynamics / rolling ------------------------------------------
    frontal_area_m2: float = 0.60
    drag_coeff: float = 0.80        # Cd (open kart, no bodywork)
    rolling_resistance: float = 0.018

    # --- Motor -----------------------------------------------------------
    motor_type: str = "DC Series"           # DC Series / DC Shunt / BLDC / PMSM
    motor_kv: float = 0.0                   # RPM/V (0 = unknown)
    motor_rated_voltage: float = 48.0       # V
    motor_rated_current: float = 300.0      # A
    motor_poles: int = 4

    # --- Battery ---------------------------------------------------------
    battery_chemistry: str = "LiPo"        # LiPo / LiFePO4 / Lead Acid / NiMH
    battery_cells_series: int = 14          # S count (14S LiPo ≈ 51.8V nominal)
    battery_capacity_ah: float = 20.0
    battery_nominal_v_per_cell: float = 3.7   # LiPo nominal; adjust for chemistry

    @property
    def total_mass_kg(self) -> float:
        return self.kart_mass_kg + self.driver_mass_kg

    @property
    def battery_nominal_voltage(self) -> float:
        return self.battery_cells_series * self.battery_nominal_v_per_cell

    @property
    def battery_capacity_kwh(self) -> float:
        return (self.battery_nominal_voltage * self.battery_capacity_ah) / 1000.0

    # ---- Cell voltage lookup for chemistry ------------------------------
    CHEMISTRY_DEFAULTS = {
        "LiPo":     {"nominal": 3.70, "full": 4.20, "empty": 3.50},
        "LiFePO4":  {"nominal": 3.20, "full": 3.65, "empty": 2.80},
        "Lead Acid":{"nominal": 2.00, "full": 2.15, "empty": 1.75},
        "NiMH":     {"nominal": 1.20, "full": 1.45, "empty": 1.00},
    }

    def cell_voltage_full(self) -> float:
        return self.CHEMISTRY_DEFAULTS.get(
            self.battery_chemistry, {"full": 4.2}
        )["full"]

    def cell_voltage_empty(self) -> float:
        return self.CHEMISTRY_DEFAULTS.get(
            self.battery_chemistry, {"empty": 3.5}
        )["empty"]

    def pack_voltage_full(self) -> float:
        return self.battery_cells_series * self.cell_voltage_full()

    def pack_voltage_empty(self) -> float:
        return self.battery_cells_series * self.cell_voltage_empty()

    # ---- I/O ------------------------------------------------------------
    def to_json(self, filepath: str) -> None:
        with open(filepath, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def from_json(cls, filepath: str) -> "VehicleConfig":
        with open(filepath, "r") as f:
            d = json.load(f)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def copy(self) -> "VehicleConfig":
        import copy
        return copy.deepcopy(self)


@dataclass
class SprintSetup:
    """A named sprocket + settings configuration for quick recall."""
    name: str = "New Setup"
    date: str = ""
    track: str = ""
    motor_sprocket_teeth: int = 11
    axle_sprocket_teeth: int = 72
    tire_diameter_in: float = 11.0
    controller_max_current: int = 300
    controller_accel_rate: int = 64
    notes: str = ""


@dataclass
class SprintSetupDatabase:
    """In-memory database of saved sprint setups."""
    setups: List[SprintSetup] = field(default_factory=list)

    def add(self, setup: SprintSetup) -> None:
        self.setups.append(setup)

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.setups):
            del self.setups[index]

    def to_json(self, filepath: str) -> None:
        with open(filepath, "w") as f:
            json.dump([asdict(s) for s in self.setups], f, indent=2)

    @classmethod
    def from_json(cls, filepath: str) -> "SprintSetupDatabase":
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls(setups=[SprintSetup(**d) for d in data])
