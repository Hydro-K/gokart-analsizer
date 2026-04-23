"""
Acceleration analysis tab.
Scatter plot of instantaneous acceleration vs speed, colored by phase.
Shows projection overlay when settings change.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QSizePolicy,
)
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from scipy.ndimage import gaussian_filter1d

CHART_BG = "#0d1b2a"
GRID_COLOR = "#1a2a3a"

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis, LapData
    from src.alltrax_settings import AlltraxSettings
    from src.gear_ratio import GearRatioConfig


class AccelTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self._cur_settings: Optional["AlltraxSettings"] = None
        self._cur_gear: Optional["GearRatioConfig"] = None
        self.figure = Figure(facecolor=CHART_BG)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        ctrl = QHBoxLayout()
        self.show_accel_cb = QCheckBox("Acceleration")
        self.show_accel_cb.setChecked(True)
        self.show_accel_cb.toggled.connect(self._replot)
        ctrl.addWidget(self.show_accel_cb)

        self.show_brake_cb = QCheckBox("Braking")
        self.show_brake_cb.setChecked(True)
        self.show_brake_cb.toggled.connect(self._replot)
        ctrl.addWidget(self.show_brake_cb)

        self.show_proj_cb = QCheckBox("Show projection")
        self.show_proj_cb.setChecked(True)
        self.show_proj_cb.toggled.connect(self._replot)
        ctrl.addWidget(self.show_proj_cb)

        self.delta_label = QLabel("")
        self.delta_label.setStyleSheet("color: #FFD700; font-weight: bold;")
        ctrl.addWidget(self.delta_label)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self.ax = self.figure.add_subplot(111)
        self._style_axes()
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        toolbar.setStyleSheet("background-color: #0f3460; color: #e0e0e0;")
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)

    def _style_axes(self) -> None:
        ax = self.ax
        ax.set_facecolor(CHART_BG)
        ax.tick_params(colors="#aaaacc", labelsize=9)
        ax.xaxis.label.set_color("#aaaacc")
        ax.yaxis.label.set_color("#aaaacc")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--")
        ax.set_xlabel("Speed (km/h)")
        ax.set_ylabel("Acceleration (m/s²)")
        ax.axhline(0, color="#555577", linewidth=0.8, linestyle="-")

    def set_session(self, analysis: "SessionAnalysis") -> None:
        self.session = analysis
        self._replot()

    def on_settings_changed(self, settings: "AlltraxSettings", gear: "GearRatioConfig") -> None:
        self._cur_settings = settings
        self._cur_gear = gear
        self._replot()

    def _compute_accel(self, lap: "LapData"):
        smooth = gaussian_filter1d(lap.speed, sigma=5)
        accel = np.gradient(smooth, lap.time)
        accel = gaussian_filter1d(accel, sigma=2)
        return accel

    def _replot(self) -> None:
        if self.session is None:
            return
        lap = self.session.best_lap
        accel = self._compute_accel(lap)
        speed_kmh = lap.speed * 3.6

        self.ax.cla()
        self._style_axes()

        if self.show_accel_cb.isChecked():
            mask = accel > 0.2
            self.ax.scatter(
                speed_kmh[mask], accel[mask],
                c="#00FF88", s=4, alpha=0.5, label="Acceleration", zorder=3,
            )

        if self.show_brake_cb.isChecked():
            mask = accel < -0.2
            self.ax.scatter(
                speed_kmh[mask], accel[mask],
                c="#FF4444", s=4, alpha=0.5, label="Braking", zorder=3,
            )

        # Projection overlay
        if self.show_proj_cb.isChecked() and self._cur_settings and self._cur_gear:
            try:
                from src.projections import project_speed_trace
                from src.alltrax_settings import AlltraxSettings as AS
                from src.gear_ratio import GearRatioConfig as GRC
                base_s = AS()
                base_g = GRC()
                proj_speed, proj_time = project_speed_trace(
                    lap, self._cur_settings, base_s, self._cur_gear, base_g
                )
                proj_accel = np.gradient(gaussian_filter1d(proj_speed, sigma=5), lap.time)
                proj_accel = gaussian_filter1d(proj_accel, sigma=2)
                proj_kmh = proj_speed * 3.6

                mask = proj_accel > 0.2
                if mask.any():
                    self.ax.scatter(
                        proj_kmh[mask], proj_accel[mask],
                        c="#FF8800", s=4, alpha=0.4, label="Projected Accel", zorder=4,
                        marker="^",
                    )

                delta = proj_time - lap.lap_time
                sign = "+" if delta >= 0 else ""
                color = "#FF4444" if delta >= 0 else "#00FF88"
                self.delta_label.setText(f"Projected Δ: {sign}{delta:.2f}s")
                self.delta_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            except Exception:
                pass

        self.ax.legend(facecolor="#0d1b2a", edgecolor="#333355", labelcolor="#e0e0e0", markerscale=3)
        self.ax.set_title(
            "Acceleration Profile — Best Lap", color="#e0e0e0", fontsize=11, pad=8
        )
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
