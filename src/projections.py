"""
Performance projection engine.

Uses a linear-perturbation model anchored to measured data:
  projected_speed = baseline_speed + Δv_from_settings_change

This avoids numerical drift while still showing correct directional changes.
"""

from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter1d
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.lap_analyzer import LapData
    from src.alltrax_settings import AlltraxSettings
    from src.gear_ratio import GearRatioConfig


def project_speed_trace(
    lap: "LapData",
    new_settings: "AlltraxSettings",
    base_settings: "AlltraxSettings",
    new_gear: "GearRatioConfig",
    base_gear: "GearRatioConfig",
) -> tuple[np.ndarray, float]:
    """
    Returns (projected_speed_ms, projected_lap_time_s).

    Scaling effects applied:
      • Max current → additional acceleration in accel zones
      • Accel rate  → ramp speed (compresses/extends early accel)
      • Regen on    → additional braking force
      • Gear ratio  → scales high-speed sections and top speed cap
      • Speed limit → hard cap
    """
    time = lap.time
    speed = lap.speed
    phase = lap.phase
    n = len(time)

    if n < 4:
        return speed.copy(), lap.lap_time

    # Time step array
    dt = np.diff(time, prepend=time[0])
    dt[0] = dt[1] if len(dt) > 1 else 1 / 25.0
    dt = np.clip(dt, 1e-6, 1.0)

    # Smooth baseline for stable gradient
    smooth = gaussian_filter1d(speed, sigma=5)
    accel = np.gradient(smooth, time)

    # --- Scaling factors ---------------------------------------------------
    current_scale = new_settings.max_current / max(1, base_settings.max_current)
    accel_rate_scale = new_settings.accel_rate / max(1, base_settings.accel_rate)
    gear_scale = base_gear.ratio / new_gear.ratio   # > 1 → higher top speed
    v_max = np.max(smooth)
    v_max_proj = v_max * gear_scale
    speed_limit_ms = (new_settings.speed_limit / 100.0) * v_max_proj

    # --- Compute additional acceleration Δa from settings changes ----------
    delta_accel = np.zeros(n)

    for i in range(n):
        ph = str(phase[i])
        a = float(accel[i])

        if ph == "accelerating" and a > 0:
            # Additional current → proportionally more torque
            extra_current = (current_scale - 1.0) * a
            # Higher accel_rate → faster ramp, but diminishes above ~2×
            extra_rate = (accel_rate_scale - 1.0) * a * 0.25
            # Back-EMF: extra torque helps less near top speed
            back_emf = max(0.0, 1.0 - smooth[i] / max(v_max_proj, 0.01))
            delta_accel[i] = (extra_current + extra_rate) * back_emf

        elif ph == "braking" and a < 0:
            if new_settings.regen_braking and not base_settings.regen_braking:
                delta_accel[i] = a * 0.12   # regen adds ~12% extra decel

    # Integrate Δa over time to get Δv
    delta_v = np.cumsum(delta_accel * dt)

    # Projected speed = baseline + perturbation
    projected = smooth + delta_v

    # Apply gear-ratio shift to high-speed sections
    if abs(gear_scale - 1.0) > 0.001:
        high_mask = smooth > v_max * 0.78
        # Interpolate smoothly: low speed unchanged, high speed scaled
        ratio = smooth / max(v_max, 0.01)
        gear_blend = np.clip((ratio - 0.78) / 0.22, 0, 1)  # 0 at v<78%, 1 at v>100%
        projected = projected + smooth * (gear_scale - 1.0) * gear_blend

    # Apply speed limit cap
    projected = gaussian_filter1d(projected, sigma=2)
    projected = np.clip(projected, 0.0, speed_limit_ms)

    # --- Estimate projected lap time via cumulative distance ---------------
    # Track has fixed length D.  Find when projected car covers D.
    cum_base = np.cumsum(smooth * dt)
    total_dist = float(cum_base[-1])
    cum_proj = np.cumsum(projected * dt)

    if cum_proj[-1] <= 0:
        projected_lap_time = lap.lap_time
    elif cum_proj[-1] < total_dist:
        # Projected is slower overall; extrapolate
        avg_ratio = total_dist / float(cum_proj[-1])
        projected_lap_time = lap.lap_time * avg_ratio
    else:
        projected_lap_time = float(np.interp(total_dist, cum_proj, time))

    return projected, projected_lap_time


def estimate_lap_delta(
    lap: "LapData",
    new_settings: "AlltraxSettings",
    base_settings: "AlltraxSettings",
    new_gear: "GearRatioConfig",
    base_gear: "GearRatioConfig",
) -> float:
    """Return estimated lap time change in seconds (negative = faster)."""
    _, proj_time = project_speed_trace(lap, new_settings, base_settings, new_gear, base_gear)
    return proj_time - lap.lap_time
