"""
Deep analysis functions used by the professional analysis tabs.
All functions are pure (no Qt imports) for testability.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
import numpy as np
from scipy.ndimage import gaussian_filter1d

if TYPE_CHECKING:
    from backend.analysis.lap_analyzer import LapData, SessionAnalysis


# ---------------------------------------------------------------------------
# Speed vs Distance
# ---------------------------------------------------------------------------

def speed_vs_distance(
    time: np.ndarray, speed: np.ndarray
) -> np.ndarray:
    """Integrate speed to get cumulative distance (m) at each sample."""
    dt = np.diff(time, prepend=time[0])
    dt[0] = dt[1] if len(dt) > 1 else 1 / 25.0
    dt = np.clip(dt, 0, 1.0)
    return np.cumsum(speed * dt)


# ---------------------------------------------------------------------------
# Sector Analysis
# ---------------------------------------------------------------------------

@dataclass
class SectorResult:
    sector_num: int
    dist_start_m: float
    dist_end_m: float
    time_s: float
    avg_speed_kmh: float
    min_speed_kmh: float
    max_speed_kmh: float


def sector_splits(
    lap: "LapData", n_sectors: int = 5
) -> List[SectorResult]:
    """Split lap into n equal-distance sectors and return per-sector stats."""
    dist = speed_vs_distance(lap.time, lap.speed)
    total = float(dist[-1])
    if total <= 0:
        return []

    boundaries = np.linspace(0, total, n_sectors + 1)
    results = []
    for i in range(n_sectors):
        d_start = boundaries[i]
        d_end = boundaries[i + 1]

        # Indices belonging to this sector
        mask = (dist >= d_start) & (dist < d_end)
        if mask.sum() < 2:
            continue

        t_start = float(np.interp(d_start, dist, lap.time))
        t_end = float(np.interp(d_end, dist, lap.time))
        seg_speed = lap.speed[mask] * 3.6  # km/h

        results.append(SectorResult(
            sector_num=i + 1,
            dist_start_m=d_start,
            dist_end_m=d_end,
            time_s=t_end - t_start,
            avg_speed_kmh=float(np.mean(seg_speed)),
            min_speed_kmh=float(np.min(seg_speed)),
            max_speed_kmh=float(np.max(seg_speed)),
        ))
    return results


def theoretical_best_lap(
    session: "SessionAnalysis", n_sectors: int = 5
) -> tuple[float, List[float], List[int]]:
    """
    Compute theoretical best lap time from best sector across all laps.

    Returns:
        (theoretical_time_s, best_sector_times, best_sector_lap_indices)
    """
    laps = session.laps
    if not laps:
        return session.best_lap.lap_time, [], []

    all_sectors: List[List[SectorResult]] = []
    for lap in laps:
        sectors = sector_splits(lap, n_sectors)
        if len(sectors) == n_sectors:
            all_sectors.append(sectors)

    if not all_sectors:
        return session.best_lap.lap_time, [], []

    best_times: List[float] = []
    best_lap_idxs: List[int] = []

    for s in range(n_sectors):
        sector_vals = [(all_sectors[l][s].time_s, l) for l in range(len(all_sectors))]
        best_t, best_l = min(sector_vals, key=lambda x: x[0])
        best_times.append(best_t)
        best_lap_idxs.append(best_l)

    return sum(best_times), best_times, best_lap_idxs


# ---------------------------------------------------------------------------
# Corner consistency across laps
# ---------------------------------------------------------------------------

@dataclass
class CornerStats:
    corner_number: int
    apex_speeds_kmh: List[float]      # one per lap
    entry_speeds_kmh: List[float]
    exit_speeds_kmh: List[float]
    best_apex_kmh: float
    avg_apex_kmh: float
    std_apex_kmh: float
    consistency_pct: float            # 100 = perfect


def corner_consistency_across_laps(
    session: "SessionAnalysis",
) -> List[CornerStats]:
    """Match corners across laps and compute consistency metrics."""
    n_corners = len(session.best_lap.corners)
    if n_corners == 0:
        return []

    results: List[CornerStats] = []

    for ci in range(n_corners):
        apex_speeds, entry_speeds, exit_speeds = [], [], []
        for lap in session.laps:
            if ci < len(lap.corners):
                c = lap.corners[ci]
                apex_speeds.append(c.apex_speed_kmh)
                entry_speeds.append(c.entry_speed_kmh)
                exit_speeds.append(c.exit_speed_kmh)

        if not apex_speeds:
            continue

        arr = np.array(apex_speeds)
        avg = float(np.mean(arr))
        std = float(np.std(arr))
        consistency = max(0.0, 100.0 - (std / avg * 100)) if avg > 0 else 100.0

        results.append(CornerStats(
            corner_number=ci + 1,
            apex_speeds_kmh=apex_speeds,
            entry_speeds_kmh=entry_speeds,
            exit_speeds_kmh=exit_speeds,
            best_apex_kmh=float(np.max(arr)),
            avg_apex_kmh=avg,
            std_apex_kmh=std,
            consistency_pct=consistency,
        ))

    return results


# ---------------------------------------------------------------------------
# Energy Analysis
# ---------------------------------------------------------------------------

@dataclass
class EnergyResult:
    total_kwh: float
    regen_kwh: float
    net_kwh: float
    avg_power_kw: float
    peak_power_kw: float
    estimated_range_km: float        # extrapolated from battery capacity
    laps_per_charge: float


def estimate_energy(
    time: np.ndarray,
    speed: np.ndarray,
    mass_kg: float = 180.0,
    battery_capacity_kwh: float = 1.2,
    regen_efficiency: float = 0.0,
    drag_coeff: float = 0.80,
    frontal_area_m2: float = 0.60,
    rolling_resistance: float = 0.018,
) -> EnergyResult:
    """Physics-based energy consumption estimate per lap."""
    dt = np.diff(time, prepend=time[0])
    dt[0] = dt[1] if len(dt) > 1 else 1 / 25.0
    dt = np.clip(dt, 0, 1.0)

    accel = np.gradient(gaussian_filter1d(speed, sigma=5), time)
    g = 9.81
    rho = 1.225  # air density kg/m³

    F_inertia = mass_kg * accel
    F_aero = 0.5 * rho * drag_coeff * frontal_area_m2 * speed ** 2
    F_rolling = mass_kg * g * rolling_resistance * np.sign(speed)

    F_total = F_inertia + F_aero + F_rolling
    P = F_total * speed  # Watts

    P_motor = np.where(P > 0, P, 0.0)      # motoring power
    P_brake = np.where(P < 0, -P, 0.0)    # braking power (positive)

    E_motor = float(np.trapezoid(P_motor, time)) / 3_600_000   # kWh
    E_regen = float(np.trapezoid(P_brake, time)) / 3_600_000 * regen_efficiency

    net_kwh = E_motor - E_regen
    lap_time = float(time[-1] - time[0])
    dist_km = float(np.trapezoid(speed, time)) / 1000.0

    avg_power_kw = net_kwh / (lap_time / 3600) if lap_time > 0 else 0.0
    peak_power_kw = float(np.max(P_motor)) / 1000.0

    laps_per_charge = battery_capacity_kwh / net_kwh if net_kwh > 0 else 0.0
    est_range_km = dist_km * laps_per_charge

    return EnergyResult(
        total_kwh=E_motor,
        regen_kwh=E_regen,
        net_kwh=net_kwh,
        avg_power_kw=avg_power_kw,
        peak_power_kw=peak_power_kw,
        estimated_range_km=est_range_km,
        laps_per_charge=laps_per_charge,
    )


# ---------------------------------------------------------------------------
# Driver smoothness
# ---------------------------------------------------------------------------

def driver_smoothness_score(time: np.ndarray, speed: np.ndarray) -> float:
    """
    Returns 0-100 smoothness score (100 = perfectly smooth).
    Based on normalised RMS of jerk (3rd derivative of position).
    """
    smooth = gaussian_filter1d(speed, sigma=8)
    accel = np.gradient(smooth, time)
    jerk = np.gradient(accel, time)
    rms_jerk = float(np.sqrt(np.mean(jerk ** 2)))
    # Typical kart jerk range: 0 (glass-smooth) to ~5 (very aggressive)
    score = max(0.0, 100.0 - rms_jerk * 25.0)
    return round(min(100.0, score), 1)


# ---------------------------------------------------------------------------
# Time delta between two laps on a distance axis
# ---------------------------------------------------------------------------

def time_delta_vs_distance(
    lap1: "LapData", lap2: "LapData", n_points: int = 1000
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns (distance_m, delta_s) where delta > 0 means lap2 is slower.
    Both laps are compared on a common distance axis.
    """
    dist1 = speed_vs_distance(lap1.time, lap1.speed)
    dist2 = speed_vs_distance(lap2.time, lap2.speed)

    d_max = min(float(dist1[-1]), float(dist2[-1]))
    d_common = np.linspace(0, d_max, n_points)

    # Time at each distance for each lap
    t1 = np.interp(d_common, dist1, lap1.time)
    t2 = np.interp(d_common, dist2, lap2.time)

    delta = t1 - t2   # positive = lap1 is slower at that point
    return d_common, delta
