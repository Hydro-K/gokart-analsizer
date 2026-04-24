"""
Session Manager — holds all loaded CSV sessions and provides
multi-session comparison.  Replaces the simple session1/session2 pattern.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import os

from src.data_loader import RawSessionData, load_aim_csv
from src.lap_analyzer import SessionAnalysis, analyse_session


@dataclass
class LoadedSession:
    raw:        RawSessionData
    analysis:   SessionAnalysis
    driver_name: str
    color:      str          # plot colour assigned by manager
    visible:    bool = True  # toggle on/off in multi-compare views

    @property
    def label(self) -> str:
        return (
            f"{self.driver_name}  ·  {self.raw.filename}  ·  "
            f"{len(self.analysis.laps)} laps  ·  best {self.analysis.best_lap.lap_time_str}"
        )


_PALETTE = [
    "#00BFFF", "#FF6B6B", "#00FF88", "#FFD700",
    "#FF8800", "#CC88FF", "#FF88CC", "#88FFCC",
    "#FFAA44", "#44AAFF",
]


class SessionManager:
    """
    Manages a list of LoadedSession objects.
    Supports bulk-loading of multiple SCCA/AiM CSV files.
    """

    def __init__(self) -> None:
        self.sessions: List[LoadedSession] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_file(self, filepath: str, driver_name: str = "") -> LoadedSession:
        """Parse one CSV and add to the session list.  Returns the new session."""
        raw = load_aim_csv(filepath)
        if driver_name:
            raw.driver_name = driver_name
        analysis = analyse_session(
            raw.time, raw.speed, raw.lat, raw.lon,
            raw.beacon, raw.has_beacon,
        )
        # Attach raw reference to analysis for downstream tabs
        analysis.raw = raw  # type: ignore[attr-defined]

        color = _PALETTE[len(self.sessions) % len(_PALETTE)]
        session = LoadedSession(
            raw=raw,
            analysis=analysis,
            driver_name=driver_name or raw.driver_name or os.path.basename(filepath),
            color=color,
        )
        self.sessions.append(session)
        return session

    def load_multiple(
        self, filepaths: List[str], driver_name: str = ""
    ) -> List[LoadedSession]:
        """Load several CSVs from the same device / event at once."""
        loaded = []
        for fp in filepaths:
            try:
                s = self.load_file(fp, driver_name)
                loaded.append(s)
            except Exception as exc:
                print(f"[SessionManager] Skipped {fp}: {exc}")
        return loaded

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.sessions):
            del self.sessions[index]
            # Re-assign colours
            for i, s in enumerate(self.sessions):
                s.color = _PALETTE[i % len(_PALETTE)]

    def clear(self) -> None:
        self.sessions.clear()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.sessions)

    def __getitem__(self, idx: int) -> LoadedSession:
        return self.sessions[idx]

    @property
    def best_session(self) -> Optional[LoadedSession]:
        if not self.sessions:
            return None
        return min(self.sessions, key=lambda s: s.analysis.best_lap.lap_time)

    def pair(self, idx_a: int, idx_b: int) -> Tuple[LoadedSession, LoadedSession]:
        return self.sessions[idx_a], self.sessions[idx_b]

    # ------------------------------------------------------------------
    # Cross-session statistics
    # ---------------------&-----------

    def all_best_laps(self) -> list:
        """Return list of (LoadedSession, LapData) for each session's best lap."""
        return [(s, s.analysis.best_lap) for s in self.sessions]

    def lap_time_summary(self) -> list[dict]:
        """Return a list of dicts suitable for table display."""
        rows = []
        for s in self.sessions:
            a = s.analysis
            rows.append({
                "driver":      s.driver_name,
                "file":        s.raw.filename,
                "laps":        len(a.laps),
                "best":        a.best_lap.lap_time,
                "best_str":    a.best_lap.lap_time_str,
                "avg":         a.avg_lap_time,
                "std":         a.std_lap_time,
                "consistency": a.consistency_pct,
                "top_speed":   a.best_lap.max_speed_kmh,
                "color":       s.color,
            })
        return rows
