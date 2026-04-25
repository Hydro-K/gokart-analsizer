"""Extract 5 numeric features from a LapData object for ML driver style classification."""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict

import numpy as np
from scipy.ndimage import gaussian_filter1d

if TYPE_CHECKING:
    from backend.analysis.lap_analyzer import LapData


def extract_features(lap: "LapData") -> Dict[str, float]:
    """
    Returns dict with keys:
      throttle_variance, braking_intensity, corner_entry_speed_avg,
      accel_consistency, smoothness_score
    All values are floats in [0, 100] or similar bounded range.
    """
    time_arr  = np.asarray(lap.time,  dtype=float)
    speed_arr = np.asarray(lap.speed, dtype=float)
    phase_arr = lap.phase if (hasattr(lap, "phase") and len(lap.phase) == len(speed_arr)) else np.array([])

    n = len(time_arr)
    if n < 10:
        return {k: 0.0 for k in ("throttle_variance", "braking_intensity",
                                   "corner_entry_speed_avg", "accel_consistency", "smoothness_score")}

    smooth   = gaussian_filter1d(speed_arr, sigma=5)
    accel    = np.gradient(smooth, time_arr)
    dt       = np.diff(time_arr, prepend=time_arr[0])
    dt       = np.clip(dt, 1e-6, 1.0)

    # 1. Throttle variance — std dev of acceleration in accelerating phase
    if len(phase_arr) == n:
        accel_mask = np.array([str(p) == "accelerating" for p in phase_arr])
    else:
        accel_mask = accel > 0.3
    accel_vals = accel[accel_mask]
    if len(accel_vals) > 3:
        throttle_variance = float(np.std(accel_vals) / max(np.mean(accel_vals), 0.01) * 10)
    else:
        throttle_variance = 5.0

    # 2. Braking intensity — mean |decel| in braking phase, normalized
    if len(phase_arr) == n:
        brake_mask = np.array([str(p) == "braking" for p in phase_arr])
    else:
        brake_mask = accel < -0.3
    brake_vals = accel[brake_mask]
    if len(brake_vals) > 3:
        braking_intensity = float(np.mean(np.abs(brake_vals)) / 10.0 * 100)
        braking_intensity = min(braking_intensity, 100.0)
    else:
        braking_intensity = 20.0

    # 3. Corner entry speed — from detected corners
    corner_entry_speeds = []
    if hasattr(lap, "corners") and lap.corners:
        for c in lap.corners:
            corner_entry_speeds.append(float(c.entry_speed) * 3.6)
    else:
        # Detect as speed minima
        from scipy.signal import find_peaks
        inv_speed = -smooth
        peaks, _ = find_peaks(inv_speed, prominence=2.0)
        for idx in peaks:
            # Entry = 0.5s before apex
            entry_t = time_arr[idx] - 0.5
            if entry_t > time_arr[0]:
                ei = np.searchsorted(time_arr, entry_t)
                corner_entry_speeds.append(float(smooth[ei]) * 3.6)
    corner_entry_speed_avg = float(np.mean(corner_entry_speeds)) if corner_entry_speeds else 40.0

    # 4. Accel consistency — CV of per-corner exit accelerations
    if hasattr(lap, "corners") and lap.corners and len(lap.corners) >= 2:
        exit_accels = []
        for c in lap.corners:
            ei = min(c.exit_idx + 5, n - 1)
            if ei < n:
                exit_accels.append(float(accel[ei]))
        if len(exit_accels) >= 2:
            mean_ea = np.mean(exit_accels)
            std_ea  = np.std(exit_accels)
            accel_consistency = float(max(0, 100 - (std_ea / max(abs(mean_ea), 0.01)) * 20))
        else:
            accel_consistency = 50.0
    else:
        accel_consistency = 50.0

    # 5. Smoothness — RMS jerk (lower = smoother = higher score)
    from backend.analysis.deep_analysis import driver_smoothness_score
    smoothness_score = float(driver_smoothness_score(time_arr, speed_arr))

    return {
        "throttle_variance":      round(min(throttle_variance, 100.0), 3),
        "braking_intensity":      round(braking_intensity, 3),
        "corner_entry_speed_avg": round(corner_entry_speed_avg, 3),
        "accel_consistency":      round(accel_consistency, 3),
        "smoothness_score":       round(smoothness_score, 3),
    }
