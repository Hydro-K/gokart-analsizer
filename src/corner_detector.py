"""
Auto-detect corners from a speed trace using local minima.
"""

from __future__ import annotations
from typing import List, TYPE_CHECKING

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

if TYPE_CHECKING:
    from src.lap_analyzer import CornerData


def detect_corners(time: np.ndarray, speed: np.ndarray) -> List["CornerData"]:
    """
    Find corners as local speed minima.  Returns CornerData list with
    entry / apex / exit indices and speeds.
    """
    from src.lap_analyzer import CornerData

    if len(speed) < 20:
        return []

    smooth = gaussian_filter1d(speed, sigma=7)

    # Find minima (invert for find_peaks)
    max_speed = np.max(smooth)
    min_speed = np.min(smooth)
    speed_range = max_speed - min_speed
    if speed_range < 0.5:
        return []

    # Prominence threshold: must drop at least 15% of range
    prominence = speed_range * 0.15
    min_distance = max(5, len(speed) // 30)

    peaks, props = find_peaks(
        -smooth,
        prominence=prominence,
        distance=min_distance,
    )

    if len(peaks) == 0:
        return []

    corners: List[CornerData] = []

    for i, apex_idx in enumerate(peaks):
        apex_speed = float(speed[apex_idx])
        apex_time = float(time[apex_idx])

        # Entry: go back until speed is rising past threshold
        entry_speed_target = apex_speed + speed_range * 0.20
        entry_idx = apex_idx
        for j in range(apex_idx - 1, max(0, apex_idx - len(speed) // 6), -1):
            if smooth[j] >= entry_speed_target:
                entry_idx = j
                break

        # Exit: go forward until speed is rising past threshold
        exit_idx = apex_idx
        for j in range(apex_idx + 1, min(len(speed), apex_idx + len(speed) // 6)):
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
                apex_time=apex_time,
                exit_time=float(time[exit_idx]),
                entry_speed=float(speed[entry_idx]),
                apex_speed=apex_speed,
                exit_speed=float(speed[exit_idx]),
            )
        )

    return corners
