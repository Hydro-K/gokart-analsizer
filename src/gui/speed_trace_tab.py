"""
Speed trace tab with:
- Color-coded phase segments (accel / braking / cornering / straight)
- Per-lap selector (best, all, specific)
- Real-time projection overlay when settings change
- Full zoom/pan via NavigationToolbar2QT + scroll-wheel zoom
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QPushButton, QCheckBox, QGroupBox, QSizePolicy,
)
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from scipy.ndimage import gaussian_filter1d

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis, LapData
    from src.alltrax_settings import AlltraxSettings
    from src.gear_ratio import GearRatioConfig

PHASE_COLORS = {
    "accelerating": "#00FF88",
    "braking":      "#FF4444",
    "cornering":    "#FFD700",
    "straight":     "#4488FF",
}

CHART_BG = "#0d1b2a"
GRID_COLOR = "#1a2a3a"


def _make_colored_collection(time, speed, phase):
    """Build a LineCollection with per-segment phase colours."""
    pts = np.array([time, speed]).T.reshape(-1, 1, 2)
    segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
    colors = [PHASE_COLORS.get(str(p), "#888888") for p in phase[:-1]]
    return LineCollection(segs, colors=colors, linewidth=2.0, zorder=3)


class SpeedTraceTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self._base_settings: Optional["AlltraxSettings"] = None
        self._base_gear: Optional["GearRatioConfig"] = None
        self._projection_line = None
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Controls row
        ctrl = QHBoxLayout()

        ctrl.addWidget(QLabel("Lap:"))
        self.lap_selector = QComboBox()
        self.lap_selector.addItem("Best Lap")
        self.lap_selector.currentIndexChanged.connect(self._replot)
        ctrl.addWidget(self.lap_selector)

        ctrl.addSpacing(20)
        self.show_all_cb = QCheckBox("Overlay all laps")
        self.show_all_cb.toggled.connect(self._replot)
        ctrl.addWidget(self.show_all_cb)

        ctrl.addSpacing(20)
        self.show_proj_cb = QCheckBox("Show projection")
        self.show_proj_cb.setChecked(True)
        self.show_proj_cb.toggled.connect(self._update_projection)
        ctrl.addWidget(self.show_proj_cb)

        ctrl.addSpacing(20)
        self.proj_delta_label = QLabel("")
        self.proj_delta_label.setStyleSheet("color: #FFD700; font-weight: bold;")
        ctrl.addWidget(self.proj_delta_label)

        ctrl.addStretch()

        # Legend
        for phase, color in PHASE_COLORS.items():
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 16px;")
            ctrl.addWidget(dot)
            ctrl.addWidget(QLabel(phase.capitalize()))

        layout.addLayout(ctrl)

        # Matplotlib figure
        self.figure = Figure(facecolor=CHART_BG)
        self.ax = self.figure.add_subplot(111)
        self._style_axes(self.ax)

        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Scroll-wheel zoom
        self.canvas.mpl_connect("scroll_event", self._on_scroll)

        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet("background-color: #0f3460; color: #e0e0e0;")

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def _style_axes(self, ax) -> None:
        ax.set_facecolor(CHART_BG)
        ax.tick_params(colors="#aaaacc", labelsize=9)
        ax.xaxis.label.set_color("#aaaacc")
        ax.yaxis.label.set_color("#aaaacc")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Speed (km/h)")

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def set_session(self, analysis: "SessionAnalysis") -> None:
        self.session = analysis
        self.lap_selector.blockSignals(True)
        self.lap_selector.clear()
        self.lap_selector.addItem(f"Best Lap (#{analysis.best_lap.lap_number})", analysis.best_lap_index)
        for i, lap in enumerate(analysis.laps):
            if i != analysis.best_lap_index:
                self.lap_selector.addItem(f"Lap {lap.lap_number}  ({lap.lap_time_str})", i)
        self.lap_selector.blockSignals(False)
        self._replot()

    def on_settings_changed(self, settings: "AlltraxSettings", gear: "GearRatioConfig") -> None:
        if self._base_settings is None:
            from src.alltrax_settings import AlltraxSettings as AS
            from src.gear_ratio import GearRatioConfig as GRC
            self._base_settings = AS()
            self._base_gear = GRC()
        self._cur_settings = settings
        self._cur_gear = gear
        self._update_projection()

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------

    def _current_lap(self) -> Optional["LapData"]:
        if self.session is None:
            return None
        idx = self.lap_selector.currentData()
        if idx is None:
            return self.session.best_lap
        return self.session.laps[idx]

    def _replot(self) -> None:
        if self.session is None:
            return
        self.ax.cla()
        self._style_axes(self.ax)
        self._projection_line = None

        if self.show_all_cb.isChecked():
            best_idx = self.session.best_lap_index
            for i, lap in enumerate(self.session.laps):
                alpha = 0.9 if i == best_idx else 0.3
                lw = 2.0 if i == best_idx else 0.8
                self.ax.plot(
                    lap.time, lap.speed * 3.6,
                    color="#00BFFF", linewidth=lw, alpha=alpha,
                    label=f"Lap {lap.lap_number}" if i != best_idx else f"★ Lap {lap.lap_number}",
                )
        else:
            lap = self._current_lap()
            if lap is not None:
                lc = _make_colored_collection(lap.time, lap.speed * 3.6, lap.phase)
                self.ax.add_collection(lc)
                self.ax.set_xlim(lap.time[0], lap.time[-1])
                self.ax.set_ylim(0, np.max(lap.speed) * 3.6 * 1.1)

                # Corner apex markers
                for c in lap.corners:
                    self.ax.axvline(c.apex_time, color="#FFD700", linewidth=0.6,
                                    alpha=0.5, linestyle=":")
                    self.ax.text(
                        c.apex_time, 1,
                        f"C{c.corner_number}", color="#FFD700", fontsize=7,
                        ha="center", va="bottom",
                        transform=self.ax.get_xaxis_transform(),
                    )

        self._update_projection()
        self.ax.set_title(
            "Speed Trace", color="#e0e0e0", fontsize=11, pad=8
        )
        self.canvas.draw_idle()

    def _update_projection(self) -> None:
        if not self.show_proj_cb.isChecked():
            if self._projection_line:
                self._projection_line.remove()
                self._projection_line = None
                self.proj_delta_label.setText("")
                self.canvas.draw_idle()
            return

        settings = getattr(self, "_cur_settings", None)
        gear = getattr(self, "_cur_gear", None)
        if settings is None or gear is None or self.session is None:
            return

        lap = self._current_lap()
        if lap is None:
            return

        if self._base_settings is None:
            from src.alltrax_settings import AlltraxSettings as AS
            from src.gear_ratio import GearRatioConfig as GRC
            self._base_settings = AS()
            self._base_gear = GRC()

        try:
            from src.projections import project_speed_trace
            proj_speed, proj_time = project_speed_trace(
                lap, settings, self._base_settings, gear, self._base_gear
            )
            if self._projection_line:
                try:
                    self._projection_line.remove()
                except Exception:
                    pass
            (self._projection_line,) = self.ax.plot(
                lap.time, proj_speed * 3.6,
                color="#FF8800", linewidth=1.8, linestyle="--",
                label="Projected", zorder=5, alpha=0.85,
            )
            delta = proj_time - lap.lap_time
            sign = "+" if delta >= 0 else ""
            color = "#FF4444" if delta >= 0 else "#00FF88"
            self.proj_delta_label.setText(
                f"Projected Δ lap time: {sign}{delta:.2f}s"
            )
            self.proj_delta_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.canvas.draw_idle()
        except Exception as exc:
            pass

    def _on_scroll(self, event) -> None:
        if event.inaxes is None:
            return
        ax = event.inaxes
        xdata, ydata = event.xdata, event.ydata
        scale = 0.85 if event.button == "up" else 1.15
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        ax.set_xlim([xdata + (x - xdata) * scale for x in xlim])
        ax.set_ylim([ydata + (y - ydata) * scale for y in ylim])
        self.canvas.draw_idle()
