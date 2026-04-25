"""Pydantic v2 request/response schemas for Strat-OS API."""
from __future__ import annotations
from typing import Optional, List, Any
from pydantic import BaseModel, field_validator, model_validator
import backend.config as cfg


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str
    role: str = "engineer"

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ("admin", "engineer", "viewer"):
            raise ValueError("role must be admin, engineer, or viewer")
        return v

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    created_at: str

class TokenOut(BaseModel):
    token: str
    user: UserOut


# ── Drivers ───────────────────────────────────────────────────────────────────

class DriverCreate(BaseModel):
    name: str
    notes: str = ""

class DriverUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None

class DriverOut(BaseModel):
    id: int
    name: str
    notes: str
    created_at: str


# ── Karts ─────────────────────────────────────────────────────────────────────

class KartCreate(BaseModel):
    name: str
    motor_type: str = "DC Series"
    battery_type: str = "LiFePO4"
    mass_kg: float = 115.0
    settings_json: str = "{}"
    gear_json: str = "{}"
    notes: str = ""

class KartUpdate(BaseModel):
    name: Optional[str] = None
    motor_type: Optional[str] = None
    battery_type: Optional[str] = None
    mass_kg: Optional[float] = None
    settings_json: Optional[str] = None
    gear_json: Optional[str] = None
    notes: Optional[str] = None

class KartOut(BaseModel):
    id: int
    name: str
    motor_type: str
    battery_type: str
    mass_kg: float
    settings_json: str
    gear_json: str
    notes: str
    created_at: str


# ── Tracks ────────────────────────────────────────────────────────────────────

class TrackCreate(BaseModel):
    name: str
    lat_center: Optional[float] = None
    lon_center: Optional[float] = None

class TrackUpdate(BaseModel):
    name: Optional[str] = None
    lat_center: Optional[float] = None
    lon_center: Optional[float] = None

class TrackOut(BaseModel):
    id: int
    name: str
    lat_center: Optional[float]
    lon_center: Optional[float]
    length_m: Optional[float]
    has_map: bool
    created_at: str

class TrackMapOut(BaseModel):
    track_id: int
    local_xy: List[List[float]]   # [[x,y], ...]  normalized 0-1000
    length_m: Optional[float]


# ── Sessions ──────────────────────────────────────────────────────────────────

SESSION_TYPES = [
    "Practice 1", "Practice 2", "Practice 3",
    "Qualifying", "Heat Race", "Main Race",
    "Endurance", "Test & Tune", "Shakedown",
]

class SessionCreate(BaseModel):
    driver_id: int
    kart_id: int
    track_id: int
    date: str
    session_type: str = "Practice 1"
    notes: str = ""

class SessionUpdate(BaseModel):
    notes: Optional[str] = None
    session_type: Optional[str] = None

class SessionOut(BaseModel):
    id: int
    driver_id: int
    kart_id: int
    track_id: int
    driver_name: str
    kart_name: str
    track_name: str
    date: str
    session_type: str
    notes: str
    lap_count: int
    best_lap_s: Optional[float]
    created_at: str


# ── Laps ──────────────────────────────────────────────────────────────────────

class LapOut(BaseModel):
    id: int
    session_id: int
    driver_id: int
    kart_id: int
    track_id: int
    lap_number: int
    lap_time_s: float
    is_valid: bool
    created_at: str

class LapTelemetryOut(BaseModel):
    lap_id: int
    time: List[float]
    speed_ms: List[float]
    lat: Optional[List[float]]
    lon: Optional[List[float]]
    phase: Optional[List[str]]
    has_gps: bool

class CornerOut(BaseModel):
    corner_index: int
    entry_speed_kmh: float
    apex_speed_kmh: float
    exit_speed_kmh: float
    entry_time_s: float
    apex_time_s: float

class SectorOut(BaseModel):
    sector_num: int
    dist_start_m: float
    dist_end_m: float
    time_s: float
    avg_speed_kmh: float
    min_speed_kmh: float
    max_speed_kmh: float

class CompareRequest(BaseModel):
    lap_ids: List[int]

class DeltaPoint(BaseModel):
    distance_m: float
    delta_s: float         # lap_ids[1] - lap_ids[0], negative = faster

class CompareOut(BaseModel):
    lap_a_id: int
    lap_b_id: int
    delta_points: List[DeltaPoint]
    lap_a_time_s: float
    lap_b_time_s: float


# ── Post-session readings ─────────────────────────────────────────────────────

class PostSessionCreate(BaseModel):
    tyre_temp_fl: Optional[float] = None
    tyre_temp_fr: Optional[float] = None
    tyre_temp_rl: Optional[float] = None
    tyre_temp_rr: Optional[float] = None
    tyre_psi_fl:  Optional[float] = None
    tyre_psi_fr:  Optional[float] = None
    tyre_psi_rl:  Optional[float] = None
    tyre_psi_rr:  Optional[float] = None
    motor_temp_c:      Optional[float] = None
    controller_temp_c: Optional[float] = None
    battery_temp_c:    Optional[float] = None
    battery_voltage_v: Optional[float] = None
    battery_soc_pct:   Optional[float] = None
    brake_temp_fl: Optional[float] = None
    brake_temp_fr: Optional[float] = None
    brake_temp_rl: Optional[float] = None
    brake_temp_rr: Optional[float] = None
    notes: str = ""

class PostSessionOut(PostSessionCreate):
    id: int
    session_id: int
    created_at: str


# ── Kart setups ───────────────────────────────────────────────────────────────

class SetupCreate(BaseModel):
    settings_json: str
    gear_json: str
    notes: str = ""

class SetupOut(BaseModel):
    id: int
    kart_id: int
    session_id: Optional[int]
    settings_json: str
    gear_json: str
    notes: str
    created_at: str


# ── Compliance ────────────────────────────────────────────────────────────────

class ComplianceItemOut(BaseModel):
    rule_name: str
    status: str       # PASS | FAIL | WARN | VERIFY
    measured: Optional[float]
    limit: Optional[float]
    message: str
    actionable: str

class ComplianceReportOut(BaseModel):
    passed: bool
    items: List[ComplianceItemOut]

class CompetitionRulesUpdate(BaseModel):
    controller_max_current_a: Optional[float] = None
    battery_voltage_max_v: Optional[float] = None
    battery_voltage_min_v: Optional[float] = None
    speed_limit_kmh: Optional[float] = None
    combined_min_weight_kg: Optional[float] = None

    @field_validator("controller_max_current_a")
    @classmethod
    def cap_current(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v > cfg.MAX_CURRENT_HARD_LIMIT:
            raise ValueError(f"Max current cannot exceed {cfg.MAX_CURRENT_HARD_LIMIT}A (EVGP rule)")
        return v


# ── Simulation ────────────────────────────────────────────────────────────────

class SimInputA(BaseModel):
    session_id: int
    lap_id: int
    max_current: int = 180
    accel_rate: int = 64
    speed_limit_pct: int = 100
    gear_ratio_new: float = 5.0
    gear_ratio_old: float = 5.0
    mass_new_kg: float = 230.0
    mass_old_kg: float = 230.0
    tyre_psi_rear: float = 10.0
    tyre_psi_front: float = 10.0
    motor_temp_c: float = 25.0

    @field_validator("max_current")
    @classmethod
    def cap_current(cls, v: int) -> int:
        return min(v, cfg.MAX_CURRENT_HARD_LIMIT)

class SimResultA(BaseModel):
    mode: str = "A"
    original_lap_time_s: float
    simulated_lap_time_s: float
    delta_s: float
    delta_pct: float
    energy_kwh: Optional[float]
    inputs: SimInputA

class SimInputC(BaseModel):
    session_id: int
    lap_id: int
    max_current: int = 180
    accel_rate: int = 64
    gear_ratio: float = 5.0
    mass_kg: float = 230.0
    tyre_psi_rear: float = 10.0
    tyre_psi_front: float = 10.0
    motor_temp_c: float = 25.0
    goal: str = "lap_time"
    weight_speed: float = 0.5
    weight_energy: float = 0.5

    @field_validator("max_current")
    @classmethod
    def cap_current(cls, v: int) -> int:
        return min(v, cfg.MAX_CURRENT_HARD_LIMIT)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "SimInputC":
        if abs(self.weight_speed + self.weight_energy - 1.0) > 0.01:
            raise ValueError("weight_speed + weight_energy must equal 1.0")
        return self

class SimResultJobOut(BaseModel):
    job_id: int
    message: str = "Mode C simulation queued"


# ── ML ────────────────────────────────────────────────────────────────────────

class DriverStyleOut(BaseModel):
    driver_id: int
    style_label: str
    confidence: float
    sessions_analyzed: int
    updated_at: str

class MLStatusOut(BaseModel):
    model_exists: bool
    n_training_samples: int
    last_trained: Optional[str]


# ── Recommendations ───────────────────────────────────────────────────────────

class RecommendationOut(BaseModel):
    category: str
    setting_key: str
    current_value: Any
    recommended_value: Any
    delta: Any
    reason: str
    predicted_outcome: str
    priority: int


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobOut(BaseModel):
    id: int
    type: str
    status: str
    priority: int
    result_json: Optional[str]
    error_msg: Optional[str]
    worker_id: Optional[str]
    created_at: str
    updated_at: str


# ── Storage ───────────────────────────────────────────────────────────────────

class StorageStatsOut(BaseModel):
    sd_total_gb: float
    sd_used_gb: float
    sd_pct: float
    hdd_available: bool
    hdd_total_gb: Optional[float]
    hdd_used_gb: Optional[float]
    threshold_warn: int
    threshold_critical: int
    threshold_emergency: int
    status: str           # ok | warn | critical | emergency
    sessions_on_sd: int
    sessions_archived: int


# ── Export ────────────────────────────────────────────────────────────────────

class ExportJobOut(BaseModel):
    job_id: int
    message: str


# ── Benchmarks ───────────────────────────────────────────────────────────────

class BenchmarkOut(BaseModel):
    track_id: int
    driver_id: int
    kart_id: int
    best_ever_s: Optional[float]
    best_session_s: Optional[float]
    theoretical_best_s: Optional[float]
    updated_at: str


# ── System ────────────────────────────────────────────────────────────────────

class SystemStatusOut(BaseModel):
    version: str
    pi_mode: bool
    db_path: str
    has_users: bool
    has_drivers: bool
    has_karts: bool
