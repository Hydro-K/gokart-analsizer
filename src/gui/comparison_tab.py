"""
Driver vs driver comparison tab.
Speed trace overlay with delta fill, corner speeds, throttle zones side by side.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QSizePolicy,
)
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d

CHART_BG = "#0d1b2a"
GRID_COLOR = "#1a2a3a"
D1_COLOR = "#00BFFF"
D2_COLOR = "#FF6B6B"

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis


class ComparisonTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session1: Optional["SessionAnalysis"] = None
        self.session2: Optional["SessionAnalysis"] = None
        self.figure = Figure(facecolor=CHART_BG)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.info_label = QLabel("Load two sessions to enable comparison")
        self.info_label.setStyleSheet("color: #8888aa; font-size: 13px; padding: 8px;")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        toolbar.setStyleSheet("background-color: #0f3460; color: #e0e0e0;")
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)

    def set_sessions(self, session1: "SessionAnalysis", session2: "SessionAnalysis") -> None:
        self.session1 = session1
        self.session2 = session2
        d1_name = getattr(getattr(session1, "raw", None), "driver_name", "Driver 1")
        d2_name = getattr(getattr(session2, "raw", None), "driver_name", "Driver 2")
        self.info_label.setText(
            f"Comparing: {d1_name} (best: {session1.best_lap.lap_time_str})  vs  "
            f"{d2_name} (best: {session2.best_lap.lap_time_str})"
        )
        self._replot(d1_name, d2_name)

    def _replot(self, d1_name: str = "Driver 1", d2_name: str = "Driver 2") -> None:
        self.figure.clear()
        gs = GridSpec(3, 2, figure=self.figure, hspace=0.45, wspace=0.35)
        ax_trace = self.figure.add_subplot(gs[0, :])
        ax_delta = self.figure.add_subplot(gs[1, :])
        ax_corners = self.figure.add_subplot(gs[2, 0])
        ax_zones = self.figure.add_subplot(gs[2, 1])

        for ax in (ax_trace, ax_delta, ax_corners, ax_zones):
            ax.set_facecolor(CHART_BG)
            ax.tick_params(colors="#aaaacc", labelsize=8)
            ax.xaxis.label.set_color("#aaaacc")
            ax.yaxis.label.set_color("#aaaacc")
            for spine in ax.spines.values():
                spine.set_edgecolor("#333355")
            ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--")

        lap1 = self.session1.best_lap
        lap2 = self.session2.best_lap

        # Speed trace overlay
        ax_trace.plot(lap1.time, lap1.speed * 3.6, color=D1_COLOR, linewidth=1.8,
                      label=d1_name, zorder=3)
        ax_trace.plot(lap2.time, lap2.speed * 3.6, color=D2_COLOR, linewidth=1.8,
                      label=d2_name, zorder=3)
        ax_trace.set_ylabel("Speed (km/h)", color="#aaaacc")
        ax_trace.set_title("Speed Trace Comparison", color="#e0e0e0", fontsize=10)
        ax_trace.legend(facecolor="#0d1b2a", edgecolor="#333355", labelcolor="#e0e0e0", fontsize=8)

        # Delta fill
        t_max = min(lap1.time[-1], lap2.time[-1])
        t_common = np.linspace(0, t_max, 2000)
        try:
            f1 = interp1d(lap1.time, lap1.speed * 3.6, bounds_error=False, fill_value="extrapolate")
            f2 = interp1d(lap2.time, lap2.speed * 3.6, bounds_error=False, fill_value="extrapolate")
            v1 = f1(t_common)
            v2 = f2(t_common)
            delta = v1 - v2
            ax_delta.axhline(0, color="#555577", linewidth=0.8)
            ax_delta.fill_between(t_common, delta, 0,
                                  where=delta >= 0, color=D1_COLOR, alpha=0.35,
                                  label=f"{d1_name} faster")
            ax_delta.fill_between(t_common, delta, 0,
                                  where=delta < 0, color=D2_COLOR, alpha=0.35,
                                  label=f"{d2_name} faster")
            ax_delta.plot(t_common, delta, color="#FFFFFF", linewidth=0.8, alpha=0.4)
        except Exception:
            ax_delta.text(0.5, 0.5, "Cannot interpolate", ha="center", va="center",
                          transform=ax_delta.transAxes, color="#888888")
        ax_delta.set_ylabel("Δ Speed (km/h)", color="#aaaacc")
        ax_delta.set_xlabel("Time (s)", color="#aaaacc")
        ax_delta.set_title("Speed Delta (positive = Driver 1 faster)", color="#e0e0e0", fontsize=10)
        ax_delta.legend(facecolor="#0d1b2a", edgecolor="#333355", labelcolor="#e0e0e0", fontsize=8)

        # Corner speeds
        c1 = lap1.corners
        c2 = lap2.corners
        n = min(len(c1), len(c2))
        if n > 0:
            x = np.arange(n)
            w = 0.35
            ax_corners.bar(x - w / 2, [c.apex_speed_kmh for c in c1[:n]], w,
                           color=D1_COLOR, alpha=0.85, label=d1_name)
            ax_corners.bar(x + w / 2, [c.apex_speed_kmh for c in c2[:n]], w,
                           color=D2_COLOR, alpha=0.85, label=d2_name)
            ax_corners.set_xticks(x)
            ax_corners.set_xticklabels([f"C{i+1}" for i in range(n)], fontsize=7)
            ax_corners.set_ylabel("Apex Speed (km/h)", color="#aaaacc")
            ax_corners.set_title("Corner Apex Speeds", color="#e0e0e0", fontsize=9)
            ax_corners.legend(facecolor="#0d1b2a", edgecolor="#333355",
                              labelcolor="#e0e0e0", fontsize=7)
        else:
            ax_corners.text(0.5, 0.5, "No corners", ha="center", va="center",
                            transform=ax_corners.transAxes, color="#888888")

        # Throttle zones
        phases = ["accelerating", "braking", "cornering", "straight"]
        colors_bar = ["#00FF88", "#FF4444", "#FFD700", "#4488FF"]
        x = np.arange(len(phases))
        w = 0.35
        for ax_val, lap, color, name in [
            (-w / 2, lap1, D1_COLOR, d1_name),
            (w / 2, lap2, D2_COLOR, d2_name),
        ]:
            total = len(lap.phase)
            vals = [(lap.phase == p).sum() / total * 100 for p in phases]
            ax_zones.bar(x + ax_val, vals, w, color=color, alpha=0.85, label=name)
        ax_zones.set_xticks(x)
        ax_zones.set_xticklabels([p[:5].capitalize() for p in phases], fontsize=7)
        ax_zones.set_ylabel("% Lap Time", color="#aaaacc")
        ax_zones.set_title("Throttle Zones", color="#e0e0e0", fontsize=9)
        ax_zones.legend(facecolor="#0d1b2a", edgecolor="#333355", labelcolor="#e0e0e0", fontsize=7)

        self.canvas.draw_idle()

    def _on_scroll(self, event) -> None:
        if event.inaxes is None:
            return
        scale = 0.85 if event.button == "up" else 1.15
        ax = event.inaxes
        xd, yd = event.xdata, event.ydata
        ax.set_xlim([xd + (x - xd) * scale for x in ax.get_xlim()])
        ax.set_ylim([yd + (y - yd) * scale for y in ax.get_ylim()])
        self.canvas.draw_idle()
