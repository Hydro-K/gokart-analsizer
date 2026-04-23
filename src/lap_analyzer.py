"""
Lap detection and timing analysis.
Supports beacon-based and GPS-based lap detection.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks


@dataclass
class CornerData:
    corner_number: int
    entry_idx: int
    apex_idx: int
    exit_idx: int
    entry_time: float
    apex_time: float
    exit_time: float
    entry_speed: float  # m/s
    apex_speed: float   # m/s
    exit_speed: float   # m/s

    @property
    def entry_speed_kmh(self) -> float:
        return self.entry_speed * 3.6

    @property
    def apex_speed_kmh(self) -> float:
        return self.apex_speed * 3.6

    @property
    def exit_speed_kmh(self) -> float:
        return self.exit_speed * 3.6


@dataclass
class LapData:
    lap_number: int
    start_idx: int      # index into original raw arrays
    end_idx: int
    lap_time: float     # seconds
    time: np.ndarray    # relative time within lap, starting at 0
    speed: np.ndarray   # m/s
    lat: np.ndarray
    lon: np.ndarray
    corners: List[CornerData] = field(default_factory=list)
    phase: np.ndarray = field(default_factory=lambda: np.array([]))  # per-sample phase label

    @property
    def lap_time_str(self) -> str:
        m = int(self.lap_time // 60)
        s = self.lap_time % 60
        return f"{m}:{s:06.3f}"

    @property
    def max_speed_kmh(self) -> float:
        return float(np.max(self.speed)) * 3.6

    @property
    def avg_speed_kmh(self) -> float:
        return float(np.mean(self.speed)) * 3.6


@dataclass
class SessionAnalysis:
    laps: List[LapData]
    best_lap_index: int       # index into laps list
    avg_lap_time: float
    std_lap_time: float
    consistency_pct: float    # 100 = perfect, lower = inconsistent

    @property
    def best_lap(self) -> LapData:
        return self.laps[self.best_lap_index]

    @property
    def valid_laps(self) -> List[LapData]:
        """Laps that are within 110% of the best lap time (filter outliers)."""
        best = self.laps[self.best_lap_index].lap_time
        return [l for l in self.laps if l.lap_time <= best * 1.10]


def compute_phases(time: np.ndarray, speed: np.ndarray) -> np.ndarray:
    """
    Return array of phase labels for each sample:
    'accelerating', 'braking', 'cornering', 'straight'
    """
    smoothed = gaussian_filter1d(speed, sigma=5)
    dt = np.diff(time, prepend=time[0])
    dt[dt <= 0] = 1e-6

    accel = np.gradient(smoothed, time)
    accel = gaussian_filter1d(accel, sigma=3)

    max_speed = np.percentile(speed, 95)
    phase = np.full(len(speed), "straight", dtype=object)
    phase[accel > 0.4] = "accelerating"
    phase[accel < -0.4] = "braking"
    # Low-speed, non-accel/braking zones = cornering
    corner_mask = (speed < max_speed * 0.65) & (phase == "straight")
    phase[corner_mask] = "cornering"
    return phase


def _detect_laps_beacon(time: np.ndarray, beacon: np.ndarray) -> List[tuple]:
    """Return list of (start_idx, end_idx) from beacon pulses."""
    # Prepend 0 so a beacon pulse at sample-0 creates a rising edge
    padded = np.concatenate([[0], beacon.astype(int)])
    edges = np.where(np.diff(padded) > 0)[0]
    if len(edges) < 2:
        return []
    laps = []
    for i in range(len(edges) - 1):
        laps.append((int(edges[i]), int(edges[i + 1]) - 1))
    return laps


def _detect_laps_speed(time: np.ndarray, speed: np.ndarray) -> List[tuple]:
    """
    Heuristic: look for repeated low-speed events near the beginning of the
    recording that match the pattern of passing through a tight chicane or
    slow corner at start/finish.  Falls back to splitting by equal duration.
    """
    # Find sustained low-speed zones (potential S/F crossing)
    smooth = gaussian_filter1d(speed, sigma=10)
    threshold = np.percentile(smooth, 15)
    low_speed = smooth < threshold

    # Find start of each low-speed region
    edges = np.where(np.diff(low_speed.astype(int)) > 0)[0]
    if len(edges) < 2:
        # Fallback: assume single lap
        return [(0, len(time) - 1)]

    # Estimate lap time from first few edge-to-edge intervals
    intervals = np.diff(time[edges])
    if len(intervals) == 0:
        return [(0, len(time) - 1)]

    # Median interval between low-speed crossings ≈ lap time
    median_interval = np.median(intervals)

    # Only keep edges separated by ~1 lap
    lap_edges = [edges[0]]
    for e in edges[1:]:
        gap = time[e] - time[lap_edges[-1]]
        if gap >= median_interval * 0.8:
            lap_edges.append(e)

    if len(lap_edges) < 2:
        return [(0, len(time) - 1)]

    laps = []
    for i in range(len(lap_edges) - 1):
        laps.append((lap_edges[i], lap_edges[i + 1]))
    return laps


def analyse_session(
    time: np.ndarray,
    speed: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    beacon: np.ndarray,
    has_beacon: bool,
) -> SessionAnalysis:
    """Main entry point: detect laps, compute phases and corners."""
    if has_beacon and np.any(beacon > 0):
        lap_bounds = _detect_laps_beacon(time, beacon)
    else:
        lap_bounds = _detect_laps_speed(time, speed)

    if not lap_bounds:
        lap_bounds = [(0, len(time) - 1)]

    laps: List[LapData] = []
    for i, (s, e) in enumerate(lap_bounds):
        t_lap = time[s:e + 1]
        v_lap = speed[s:e + 1]
        la_lap = lat[s:e + 1]
        lo_lap = lon[s:e + 1]
        if len(t_lap) < 2:
            continue
        lap_time = float(t_lap[-1] - t_lap[0])
        if lap_time < 5.0:  # skip tiny fragments
            continue
        phase = compute_phases(t_lap, v_lap)
        ld = LapData(
            lap_number=i + 1,
            start_idx=s,
            end_idx=e,
            lap_time=lap_time,
            time=t_lap - t_lap[0],
            speed=v_lap,
            lat=la_lap,
            lon=lo_lap,
            phase=phase,
        )
        from src.corner_detector import detect_corners
        ld.corners = detect_corners(ld.time, ld.speed)
        laps.append(ld)

    if not laps:
        # Treat entire recording as one lap
        phase = compute_phases(time, speed)
        lap_time = float(time[-1] - time[0])
        ld = LapData(
            lap_number=1,
            start_idx=0,
            end_idx=len(time) - 1,
            lap_time=lap_time,
            time=time - time[0],
            speed=speed,
            lat=lat,
            lon=lon,
            phase=phase,
        )
        from src.corner_detector import detect_corners
        ld.corners = detect_corners(ld.time, ld.speed)
        laps = [ld]

    lap_times = np.array([l.lap_time for l in laps])
    best_idx = int(np.argmin(lap_times))
    avg = float(np.mean(lap_times))
    std = float(np.std(lap_times))
    consistency = max(0.0, 100.0 - (std / avg * 100)) if avg > 0 else 100.0

    return SessionAnalysis(
        laps=laps,
        best_lap_index=best_idx,
        avg_lap_time=avg,
        std_lap_time=std,
        consistency_pct=consistency,
    )
