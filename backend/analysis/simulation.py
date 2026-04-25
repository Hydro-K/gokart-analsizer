"""
Strat-OS Simulation Engine.

Mode A — Fast linear perturbation (sync, <100ms).
  Ported directly from gui/simulation_tab.py:_simulate_lap().
  220A hard cap enforced at entry.

Mode C — Physics ODE (async job, 2-5s on Pi).
  Uses scipy.integrate.solve_ivp with RK23 solver.
  State: [x (distance), v (speed), E (energy Wh)].
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.ndimage import gaussian_filter1d

if TYPE_CHECKING:
    from backend.analysis.lap_analyzer import LapData
    from backend.analysis.alltrax_settings import AlltraxSettings
    from backend.analysis.gear_ratio import GearRatioConfig
    from backend.analysis.vehicle_config import VehicleConfig

_MAX_CURRENT = 220  # EVGP hard limit — never exceed


@dataclass
class SimResultC:
    lap_time_s: float
    energy_kwh: float
    delta_array: np.ndarray   # simulated_speed - actual_speed, per distance point


# ── Mode A ────────────────────────────────────────────────────────────────────

def simulate_mode_a(
    lap: "LapData",
    max_current: int,
    accel_rate: int,
    speed_limit_pct: int,
    gear_ratio_new: float,
    gear_ratio_old: float,
    mass_new_kg: float,
    mass_old_kg: float,
    tyre_psi_rear: float,
    tyre_psi_front: float,
    motor_temp_c: float,
) -> tuple[np.ndarray, float]:
    """
    Physics-based lap simulation anchored to actual driver data.
    Same-driver assumption: brake points and cornering lines unchanged.
    Returns (simulated_speed_ms, simulated_lap_time_s).
    220A hard cap applied at entry.
    """
    # Hard cap — EVGP rule, never negotiate
    max_current = min(max_current, _MAX_CURRENT)

    time  = np.asarray(lap.time, dtype=float)
    speed = np.asarray(lap.speed, dtype=float)
    phase = lap.phase if hasattr(lap, "phase") and len(lap.phase) == len(speed) else np.array(["straight"] * len(speed))
    n     = len(time)

    if n < 2:
        return speed.copy(), float(lap.lap_time)

    dt = np.diff(time, prepend=time[0])
    dt[0] = dt[1] if len(dt) > 1 else 1 / 25.0
    dt = np.clip(dt, 1e-6, 1.0)

    smooth          = gaussian_filter1d(speed, sigma=5)
    accel_baseline  = np.gradient(smooth, time)
    v_max_actual    = float(np.max(smooth)) if np.max(smooth) > 0 else 1.0

    # 1. Current / torque scaling
    base_current  = 300
    current_scale = (max_current / base_current) ** 0.65

    # Motor thermal derating above 70°C
    if motor_temp_c > 70:
        thermal_factor = max(0.6, 1.0 - (motor_temp_c - 70) * 0.004)
        current_scale *= thermal_factor

    accel_rate_scale = accel_rate / 64.0

    # 2. Gear ratio → top speed shift
    gear_ratio_old = max(gear_ratio_old, 0.01)
    gear_ratio_new = max(gear_ratio_new, 0.01)
    gear_scale     = gear_ratio_old / gear_ratio_new
    v_max_proj     = v_max_actual * gear_scale
    speed_limit_ms = (speed_limit_pct / 100.0) * v_max_proj

    # 3. Mass scaling
    mass_ratio = mass_old_kg / max(mass_new_kg, 1.0)

    # 4. Tyre PSI effects
    psi_ref_rear   = 16.0
    psi_ref_front  = 15.0
    cr_scale_rear  = (psi_ref_rear  / max(tyre_psi_rear,  1.0)) ** 0.3
    cr_scale_front = (psi_ref_front / max(tyre_psi_front, 1.0)) ** 0.3
    cr_scale = (cr_scale_rear + cr_scale_front) / 2.0

    def grip_factor(psi: float, psi_opt: float = 16.0) -> float:
        deviation = abs(psi - psi_opt) / psi_opt
        return max(0.7, 1.0 - deviation ** 1.5 * 0.4)

    avg_grip = (grip_factor(tyre_psi_rear, 16.0) + grip_factor(tyre_psi_front, 15.0)) / 2.0

    # 5. Build perturbation
    delta_accel = np.zeros(n)
    for i in range(n):
        ph = str(phase[i]) if i < len(phase) else "straight"
        a  = float(accel_baseline[i])
        if ph == "accelerating" and a > 0:
            back_emf   = max(0.0, 1.0 - smooth[i] / max(v_max_proj, 0.01))
            extra_cur  = (current_scale - 1.0) * a * back_emf
            extra_rate = (accel_rate_scale - 1.0) * a * 0.20 * back_emf
            extra_mass = (mass_ratio - 1.0) * a * 0.5
            extra_cr   = (1.0 - cr_scale) * a * 0.15
            delta_accel[i] = extra_cur + extra_rate + extra_mass + extra_cr
        elif ph == "cornering":
            grip_delta = avg_grip - 1.0
            delta_accel[i] = a * grip_delta * 0.5
        elif ph == "braking" and a < 0:
            extra_mass_brake = (1.0 - mass_ratio) * abs(a) * 0.3
            delta_accel[i] = -extra_mass_brake

    delta_v   = np.cumsum(delta_accel * dt)
    simulated = smooth + delta_v

    # Apply gear ratio straight-speed scaling
    if abs(gear_scale - 1.0) > 0.001:
        ratio_arr  = smooth / max(v_max_actual, 0.01)
        gear_blend = np.clip((ratio_arr - 0.70) / 0.30, 0.0, 1.0)
        simulated += smooth * (gear_scale - 1.0) * gear_blend

    simulated = gaussian_filter1d(simulated, sigma=2)
    simulated = np.clip(simulated, 0.0, max(speed_limit_ms, 0.1))

    # 6. Estimate simulated lap time
    cum_actual = np.cumsum(smooth * dt)
    total_dist = float(cum_actual[-1])
    cum_sim    = np.cumsum(simulated * dt)

    if cum_sim[-1] <= 0:
        sim_lap_time = float(lap.lap_time)
    elif cum_sim[-1] < total_dist:
        sim_lap_time = float(lap.lap_time) * (total_dist / float(cum_sim[-1]))
    else:
        sim_lap_time = float(np.interp(total_dist, cum_sim, time))

    return simulated, sim_lap_time


# ── Mode C ────────────────────────────────────────────────────────────────────

def simulate_mode_c(
    lap: "LapData",
    settings: "AlltraxSettings",
    gear: "GearRatioConfig",
    vehicle: "VehicleConfig",
    tyre_psi_rear: float = 10.0,
    tyre_psi_front: float = 10.0,
    motor_temp_c: float = 25.0,
    weight_lap_time: float = 0.5,
    weight_energy: float = 0.5,
) -> SimResultC:
    """
    ODE physics simulation.
    State vector: [x (m), v (m/s), E (Wh)]
    Driver phase sequence replayed from actual lap.
    220A hard cap enforced.
    """
    from scipy.integrate import solve_ivp

    max_current = min(int(settings.max_current), _MAX_CURRENT)

    time_arr  = np.asarray(lap.time, dtype=float)
    speed_arr = np.asarray(lap.speed, dtype=float)
    phase_arr = lap.phase if hasattr(lap, "phase") and len(lap.phase) == len(speed_arr) else np.array(["straight"] * len(speed_arr))
    n = len(time_arr)

    if n < 2:
        return SimResultC(lap_time_s=float(lap.lap_time), energy_kwh=0.0, delta_array=np.zeros(1))

    dt_arr  = np.diff(time_arr, prepend=time_arr[0])
    dt_arr  = np.clip(dt_arr, 1e-6, 1.0)
    dist_arr = np.cumsum(speed_arr * dt_arr)
    total_dist = float(dist_arr[-1])

    # Vehicle parameters
    mass_kg      = max(vehicle.kart_mass_kg + 80.0, 100.0)  # kart + driver
    motor_kv     = 100.0     # rough KV constant (rpm/V)
    voltage      = 51.2      # nominal pack voltage
    wheel_radius = getattr(gear, "tire_radius_m", 0.18)
    efficiency   = 0.82

    # Thermal derating
    thermal = 1.0 if motor_temp_c <= 70 else max(0.6, 1.0 - (motor_temp_c - 70) * 0.004)
    effective_current = max_current * thermal

    # Rolling resistance coeff — affected by tyre PSI
    cr_base   = 0.015
    psi_ratio = (tyre_psi_rear / 16.0 + tyre_psi_front / 15.0) / 2.0
    cr        = cr_base / max(psi_ratio ** 0.3, 0.5)

    # Aero
    rho = 1.225
    Cd  = getattr(vehicle, "drag_coeff", 0.4)
    A   = getattr(vehicle, "frontal_area_m2", 0.5)

    # Build phase lookup vs distance
    phase_vs_dist = np.interp(
        np.linspace(0, total_dist, n),
        dist_arr,
        np.arange(n)
    )

    def get_phase_at(x: float) -> str:
        idx = int(np.clip(np.searchsorted(dist_arr, x), 0, n - 1))
        return str(phase_arr[idx]) if idx < len(phase_arr) else "straight"

    def odes(t_sim: float, state: list) -> list:
        x, v, E = state
        v = max(v, 0.0)
        ph = get_phase_at(x)
        back_emf_factor = max(0.0, 1.0 - v / max(total_dist / float(lap.lap_time) * 1.5, 1.0))
        if ph == "accelerating":
            F_motor = (effective_current * efficiency * voltage * back_emf_factor) / max(v + 0.1, 0.1)
        elif ph == "braking":
            F_motor = -(mass_kg * 6.0)  # strong braking
        else:
            F_motor = 0.0
        F_drag    = 0.5 * rho * Cd * A * v ** 2
        F_rolling = cr * mass_kg * 9.81
        F_net     = F_motor - F_drag - F_rolling
        a = F_net / mass_kg
        dv_dt = float(a)
        dx_dt = float(v)
        power  = max(F_motor * v, 0.0)
        dE_dt  = power / 3600.0  # W → Wh/s
        return [dx_dt, dv_dt, dE_dt]

    v0      = float(speed_arr[0])
    t_span  = (0.0, float(lap.lap_time) * 3.0)  # allow up to 3× real time
    t_eval  = np.linspace(0, float(lap.lap_time) * 1.5, max(n, 500))

    try:
        sol = solve_ivp(odes, t_span, [0.0, v0, 0.0],
                        method="RK23", t_eval=t_eval,
                        events=lambda t, y, *_: y[0] - total_dist,
                        max_step=0.2, dense_output=False)
    except Exception:
        # Fallback to Mode A estimate
        _, lap_time = simulate_mode_a(
            lap, max_current, int(getattr(settings, "accel_rate", 64)), 100,
            float(getattr(gear, "gear_ratio", 5.0)), float(getattr(gear, "gear_ratio", 5.0)),
            mass_kg, mass_kg, tyre_psi_rear, tyre_psi_front, motor_temp_c,
        )
        return SimResultC(lap_time_s=lap_time, energy_kwh=0.0, delta_array=np.zeros(1))

    # Find when x = total_dist
    x_arr = sol.y[0]
    t_arr = sol.t
    E_arr = sol.y[2]
    v_sim = sol.y[1]

    if x_arr[-1] >= total_dist:
        lap_time_s = float(np.interp(total_dist, x_arr, t_arr))
        energy_kwh = float(np.interp(total_dist, x_arr, E_arr)) / 1000.0
    else:
        # Didn't reach end — extrapolate
        avg_v = float(np.mean(np.abs(v_sim[v_sim > 0]))) if np.any(v_sim > 0) else 1.0
        remaining = total_dist - float(x_arr[-1])
        lap_time_s = float(t_arr[-1]) + remaining / avg_v
        energy_kwh = float(E_arr[-1]) / 1000.0

    # Delta array: simulated speed vs distance
    dist_sim = np.interp(np.linspace(0, total_dist, n), x_arr, np.abs(v_sim))
    delta_arr = dist_sim - speed_arr

    return SimResultC(
        lap_time_s=round(lap_time_s, 3),
        energy_kwh=round(energy_kwh, 4),
        delta_array=delta_arr,
    )
