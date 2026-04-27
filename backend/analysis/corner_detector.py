"""
Auto-detect corners from a speed trace using local minima.
"""

from __future__ import annotations
from typing import List, TYPE_CHECKING

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

if TYPE_CHECKING:
    from backend.analysis.lap_analyzer import CornerData


def detect_corners(time: np.ndarray, speed: np.ndarray) -> List["CornerData"]:
    """
    Find corners as local speed minima.  Returns CornerData list with
    entry / apex / exit indices and speeds.
    """
    from backend.analysis.lap_analyzer import CornerData

    if len(speed) < 20:
        return []

    # Smooth more aggressively so short bumps don't look like corners
    smooth = gaussian_filter1d(speed, sigma=5)

    max_speed = float(np.max(smooth))
    min_speed = float(np.min(smooth))
    speed_range = max_speed - min_speed

    if speed_range < 0.3:   # virtually constant speed — no corners possible
        return []

    # Try progressively lower prominence thresholds until we find corners.
    # Start at 10 % of range (generous for tracks with gentle curves),
    # fall back to 5 % if nothing found.
    # min_distance: no two corner apexes within 2 s of each other.
    dt = float(np.median(np.diff(time))) if len(time) > 1 else 0.1
    dt = max(dt, 0.01)
    min_dist_samples = max(5, int(2.0 / dt))   # 2 s between apexes

    peaks: np.ndarray = np.array([], dtype=int)
    for prom_frac in (0.10, 0.06, 0.03):
        prominence = speed_range * prom_frac
        peaks, _ = find_peaks(-smooth, prominence=prominence, distance=min_dist_samples)
        if len(peaks) > 0:
            break

    if len(peaks) == 0:
        return []

    corners: List[CornerData] = []
    entry_target_frac = 0.15   # entry/exit threshold: 15 % of range above apex

    for i, apex_idx in enumerate(peaks):
        apex_speed = float(speed[apex_idx])
        entry_speed_target = apex_speed + speed_range * entry_target_frac

        # Entry: step backward until speed exceeds threshold (or hit boundary)
        entry_idx = max(0, apex_idx - 1)
        for j in range(apex_idx - 1, max(0, apex_idx - min_dist_samples * 3), -1):
            if smooth[j] >= entry_speed_target:
                entry_idx = j
                break

        # Exit: step forward until speed exceeds threshold (or hit boundary)
        exit_idx = min(len(speed) - 1, apex_idx + 1)
        for j in range(apex_idx + 1, min(len(speed), apex_idx + min_dist_samples * 3)):
            if smooth[j] >= entry_speed_target:
                exit_idx = j
                break

        corners.append(
            CornerData(
                corner_number=i + 1,
                entry_idx=int(entry_idx),
                apex_idx=int(apex_idx),
                exit_idx=int(exit_idx),
                entry_time=float(time[entry_idx]),
                apex_time=float(time[apex_idx]),
                exit_time=float(time[exit_idx]),
                entry_speed=float(speed[entry_idx]),
                apex_speed=apex_speed,
                exit_speed=float(speed[exit_idx]),
            )
        )

    return corners
