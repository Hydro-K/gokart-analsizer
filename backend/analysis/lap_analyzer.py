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
    lat: np.ndarray = field(default_factory=lambda: np.array([]))
    lon: np.ndarray = field(default_factory=lambda: np.array([]))
    corners: List[CornerData] = field(default_factory=list)
    phase: np.ndarray = field(default_factory=lambda: np.array([]))  # per-sample phase label
    abs_start_s: float = 0.0   # seconds from session start (t=0) to lap start crossing

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
    best_lap_index: int = 0
    avg_lap_time: float = 0.0
    std_lap_time: float = 0.0
    consistency_pct: float = 100.0

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
    """Return list of (start_idx, end_idx) from beacon pulses.

    AiM beacon fires at the start/finish line crossing — both the END of the
    current lap and the START of the next one.  The loop between consecutive
    edges captures laps 2..N, but lap 1 (from t=0 to the first crossing) is
    always dropped by the naive range(len-1) loop.  We add it back here if
    its duration is plausible (≥ 60 % of the median inter-beacon interval).
    """
    padded = np.concatenate([[0], beacon.astype(int)])
    edges = np.where(np.diff(padded) > 0)[0]
    if len(edges) < 2:
        return []

    # Core segments: between consecutive beacon edges
    laps: List[tuple] = []
    for i in range(len(edges) - 1):
        laps.append((int(edges[i]), int(edges[i + 1]) - 1))

    if not laps:
        return [(0, len(time) - 1)]

    median_lap_t = float(np.median([time[e] - time[s] for s, e in laps]))

    # Prepend the first lap if [0 → first_edge] is ≥ 85% of a typical lap
    # (below 85% it's an out-lap / warmup fragment, not a full timed lap)
    first_seg_t = float(time[edges[0]] - time[0])
    if first_seg_t >= median_lap_t * 0.85:
        laps.insert(0, (0, int(edges[0]) - 1))

    # Append the final lap if [last_edge → end] is ≥ 85% of a typical lap
    last_seg_t = float(time[-1] - time[edges[-1]])
    if last_seg_t >= median_lap_t * 0.85:
        laps.append((int(edges[-1]), len(time) - 1))

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

    # Include the tail segment if it looks like a full lap
    if laps:
        median_lap_t = float(np.median([time[e] - time[s] for s, e in laps]))
        tail_t = float(time[-1] - time[lap_edges[-1]])
        if tail_t >= median_lap_t * 0.6:
            laps.append((lap_edges[-1], len(time) - 1))

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

    raw_laps: List[LapData] = []
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
            abs_start_s=float(t_lap[0]),
        )
        from backend.analysis.corner_detector import detect_corners
        ld.corners = detect_corners(ld.time, ld.speed)
        raw_laps.append(ld)

    # Dynamic outlier filter: removes inter-session transition fragments and
    # very long out-lap sessions that aren't real racing laps.
    # Uses IQR on the lower end so partial out-laps (e.g. 24s when typical is 37s)
    # are excluded, keeping genuinely slow laps (spins, traffic) on the upper end.
    laps: List[LapData] = raw_laps
    if len(raw_laps) >= 2:
        lap_times_arr = np.array([l.lap_time for l in raw_laps])
        median_t = float(np.median(lap_times_arr))
        q1 = float(np.percentile(lap_times_arr, 25))
        q3 = float(np.percentile(lap_times_arr, 75))
        iqr = q3 - q1 if q3 > q1 else median_t * 0.2
        # Lower fence: IQR method but never below 70% of median — anything shorter is a partial lap
        lo_cut = max(median_t * 0.70, q1 - 1.5 * iqr)
        # Upper fence: generous — 8× median removes multi-hour out-lap sessions
        hi_cut = median_t * 8.0
        filtered = [l for l in raw_laps if lo_cut <= l.lap_time <= hi_cut]
        laps = filtered if filtered else raw_laps  # fallback: keep all

    # Re-number laps sequentially after filtering
    for idx, l in enumerate(laps):
        l.lap_number = idx + 1

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
        from backend.analysis.corner_detector import detect_corners
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
