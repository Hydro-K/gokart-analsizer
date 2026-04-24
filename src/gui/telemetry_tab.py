"""
Telemetry Tab — GPS track map, time-delta-vs-distance, energy analysis.
Works with or without GPS (graceful fallback to estimated distance).
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QGroupBox, QGridLayout, QTabWidget, QSizePolicy,
)
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.colorbar import Colorbar

from src.deep_analysis import (
    speed_vs_distance, time_delta_vs_distance, estimate_energy,
)

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis, LapData

CHART_BG = "#0d1b2a"
GRID_C   = "#1a2a3a"


def _style(ax):
    ax.set_facecolor(CHART_BG)
    ax.tick_params(colors="#aaaacc", labelsize=8)
    ax.xaxis.label.set_color("#aaaacc")
    ax.yaxis.label.set_color("#aaaacc")
    for sp in ax.spines.values():
        sp.set_edgecolor("#333355")
    ax.grid(True, color=GRID_C, linewidth=0.5, linestyle="--")


def _scroll(canvas):
    def _h(ev):
        if ev.inaxes is None:
            return
        sc = 0.85 if ev.button == "up" else 1.15
        ax = ev.inaxes
        xd, yd = ev.xdata, ev.ydata
        ax.set_xlim([xd + (x - xd) * sc for x in ax.get_xlim()])
        ax.set_ylim([yd + (y - yd) * sc for y in ax.get_ylim()])
        canvas.draw_idle()
    canvas.mpl_connect("scroll_event", _h)


# ---------------------------------------------------------------------------
# GPS Track Map
# ---------------------------------------------------------------------------

class _TrackMapTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self.figure = Figure(facecolor=CHART_BG)
        layout = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Lap:"))
        self._lap_sel = QComboBox()
        self._lap_sel.currentIndexChanged.connect(self._plot)
        ctrl.addWidget(self._lap_sel)
        ctrl.addStretch()
        self._no_gps_lbl = QLabel("")
        self._no_gps_lbl.setStyleSheet("color: #FFD700;")
        ctrl.addWidget(self._no_gps_lbl)
        layout.addLayout(ctrl)

        self.canvas = FigureCanvasQTAgg(self.figure)
        _scroll(self.canvas)
        tb = NavigationToolbar2QT(self.canvas, self)
        tb.setStyleSheet("background-color: #0f3460;")
        layout.addWidget(tb)
        layout.addWidget(self.canvas)

    def set_session(self, s: "SessionAnalysis"):
        self.session = s
        self._lap_sel.blockSignals(True)
        self._lap_sel.clear()
        self._lap_sel.addItem(f"Best Lap (#{s.best_lap.lap_number})",
                              s.best_lap_index)
        for i, lap in enumerate(s.laps):
            if i != s.best_lap_index:
                self._lap_sel.addItem(f"Lap {lap.lap_number}  ({lap.lap_time_str})", i)
        self._lap_sel.blockSignals(False)
        self._plot()

    def _plot(self):
        if not self.session:
            return
        idx = self._lap_sel.currentData()
        if idx is None:
            idx = self.session.best_lap_index
        lap = self.session.laps[idx]

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(CHART_BG)
        ax.set_aspect("equal")
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(colors="#aaaacc", labelsize=7)
        ax.set_title(
            f"Track Map — Lap {lap.lap_number} (coloured by speed)",
            color="#e0e0e0", fontsize=10
        )

        has_gps = np.any(lap.lat != 0) and np.any(lap.lon != 0)
        if has_gps:
            self._no_gps_lbl.setText("")
            # Convert lat/lon to metres (local approximation)
            lat0 = float(np.mean(lap.lat))
            lon0 = float(np.mean(lap.lon))
            x = (lap.lon - lon0) * np.cos(np.radians(lat0)) * 111_320
            y = (lap.lat - lat0) * 111_320
        else:
            self._no_gps_lbl.setText("⚠ No GPS in this file — showing distance/heading estimate")
            # Fake circular track from distance integration
            dist = speed_vs_distance(lap.time, lap.speed)
            total = dist[-1]
            angle = dist / total * 2 * np.pi
            x = np.cos(angle) * 100
            y = np.sin(angle) * 100

        speed_kmh = lap.speed * 3.6
        pts = np.array([x, y]).T.reshape(-1, 1, 2)
        segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
        lc = LineCollection(segs, cmap="plasma",
                            norm=matplotlib.colors.Normalize(
                                vmin=speed_kmh.min(), vmax=speed_kmh.max()),
                            linewidth=3, zorder=3)
        lc.set_array(speed_kmh[:-1])
        ax.add_collection(lc)
        ax.autoscale()

        cb = self.figure.colorbar(lc, ax=ax, fraction=0.03, pad=0.04)
        cb.set_label("Speed (km/h)", color="#aaaacc")
        cb.ax.yaxis.set_tick_params(color="#aaaacc")
        plt_labels = [t.get_text() for t in cb.ax.get_yticklabels()]
        cb.ax.set_yticklabels(plt_labels, color="#aaaacc")

        # Mark corner apices
        for c in lap.corners:
            ci = c.apex_idx
            if has_gps:
                ax.plot(x[ci], y[ci], "^", color="#FFD700", markersize=8, zorder=5)
                ax.annotate(f"C{c.corner_number}",
                            (x[ci], y[ci]), textcoords="offset points",
                            xytext=(4, 4), color="#FFD700", fontsize=7)
            else:
                ax.plot(x[ci], y[ci], "^", color="#FFD700", markersize=8, zorder=5)

        ax.set_xlabel("East (m)" if has_gps else "", color="#aaaacc")
        ax.set_ylabel("North (m)" if has_gps else "", color="#aaaacc")
        self.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Time delta vs distance
# ---------------------------------------------------------------------------

class _DeltaTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self.figure = Figure(facecolor=CHART_BG)
        layout = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Lap A (reference):"))
        self._sel_a = QComboBox()
        ctrl.addWidget(self._sel_a)
        ctrl.addWidget(QLabel("vs Lap B:"))
        self._sel_b = QComboBox()
        ctrl.addWidget(self._sel_b)
        go_btn = matplotlib.backends.backend_qt5agg.FigureCanvasQTAgg  # placeholder
        from PyQt5.QtWidgets import QPushButton
        run = QPushButton("Compare")
        run.clicked.connect(self._plot)
        ctrl.addWidget(run)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self.canvas = FigureCanvasQTAgg(self.figure)
        _scroll(self.canvas)
        tb = NavigationToolbar2QT(self.canvas, self)
        tb.setStyleSheet("background-color: #0f3460;")
        layout.addWidget(tb)
        layout.addWidget(self.canvas)

    def set_session(self, s: "SessionAnalysis"):
        self.session = s
        for sel in (self._sel_a, self._sel_b):
            sel.blockSignals(True)
            sel.clear()
            for i, lap in enumerate(s.laps):
                marker = "★ " if i == s.best_lap_index else ""
                sel.addItem(f"{marker}Lap {lap.lap_number} ({lap.lap_time_str})", i)
            sel.blockSignals(False)
        # Default: A = best, B = worst
        self._sel_a.setCurrentIndex(0)
        worst = int(np.argmax([l.lap_time for l in s.laps]))
        self._sel_b.setCurrentIndex(worst)
        self._plot()

    def _plot(self):
        if not self.session:
            return
        ia = self._sel_a.currentData()
        ib = self._sel_b.currentData()
        if ia is None or ib is None or ia == ib:
            return
        la = self.session.laps[ia]
        lb = self.session.laps[ib]
        dist, delta = time_delta_vs_distance(la, lb)

        self.figure.clear()
        ax_speed = self.figure.add_subplot(211)
        ax_delta = self.figure.add_subplot(212)
        _style(ax_speed); _style(ax_delta)

        dist_a = speed_vs_distance(la.time, la.speed)
        dist_b = speed_vs_distance(lb.time, lb.speed)
        d_max = min(dist_a[-1], dist_b[-1])
        d_common = np.linspace(0, d_max, 2000)
        from scipy.interpolate import interp1d
        fa = interp1d(dist_a, la.speed * 3.6, bounds_error=False, fill_value="extrapolate")
        fb = interp1d(dist_b, lb.speed * 3.6, bounds_error=False, fill_value="extrapolate")

        ax_speed.plot(d_common, fa(d_common), color="#00BFFF", linewidth=1.8,
                      label=f"Lap {la.lap_number} ({la.lap_time_str})")
        ax_speed.plot(d_common, fb(d_common), color="#FF6B6B", linewidth=1.8,
                      label=f"Lap {lb.lap_number} ({lb.lap_time_str})")
        ax_speed.set_ylabel("Speed (km/h)", color="#aaaacc")
        ax_speed.set_title("Speed vs Distance Comparison", color="#e0e0e0", fontsize=10)
        ax_speed.legend(facecolor="#0d1b2a", edgecolor="#333355",
                        labelcolor="#e0e0e0", fontsize=8)

        ax_delta.axhline(0, color="#555577", linewidth=0.8)
        ax_delta.fill_between(dist, delta, 0,
                              where=(delta > 0), color="#FF4444", alpha=0.4,
                              label=f"Lap {la.lap_number} slower")
        ax_delta.fill_between(dist, delta, 0,
                              where=(delta < 0), color="#00FF88", alpha=0.4,
                              label=f"Lap {la.lap_number} faster")
        ax_delta.plot(dist, delta, color="#FFFFFF", linewidth=0.7, alpha=0.5)
        ax_delta.set_xlabel("Distance (m)", color="#aaaacc")
        ax_delta.set_ylabel("Δ Time (s)", color="#aaaacc")
        ax_delta.set_title(
            f"Time Delta: Lap {la.lap_number} vs Lap {lb.lap_number} "
            f"(+ve = A slower at that track point)",
            color="#e0e0e0", fontsize=9
        )
        ax_delta.legend(facecolor="#0d1b2a", edgecolor="#333355",
                        labelcolor="#e0e0e0", fontsize=8)
        self.figure.tight_layout(pad=1.5)
        self.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------

class _EnergyTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self.figure = Figure(facecolor=CHART_BG)
        layout = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Vehicle mass (kg):"))
        from PyQt5.QtWidgets import QDoubleSpinBox
        self._mass = QDoubleSpinBox()
        self._mass.setRange(100, 400)
        self._mass.setValue(185)
        self._mass.setSuffix(" kg")
        self._mass.valueChanged.connect(self._update)
        ctrl.addWidget(self._mass)

        ctrl.addWidget(QLabel("Battery capacity (kWh):"))
        self._cap = QDoubleSpinBox()
        self._cap.setRange(0.1, 10)
        self._cap.setSingleStep(0.1)
        self._cap.setValue(1.4)
        self._cap.setSuffix(" kWh")
        self._cap.valueChanged.connect(self._update)
        ctrl.addWidget(self._cap)

        ctrl.addWidget(QLabel("Regen efficiency:"))
        self._regen = QDoubleSpinBox()
        self._regen.setRange(0, 0.8)
        self._regen.setSingleStep(0.05)
        self._regen.setValue(0.0)
        self._regen.setSuffix(" (0–0.8)")
        self._regen.valueChanged.connect(self._update)
        ctrl.addWidget(self._regen)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet(
            "background-color: #0d1b2a; border: 1px solid #333355; "
            "border-radius: 4px; padding: 8px; font-family: monospace; "
            "color: #e0e0e0; font-size: 12px;"
        )
        layout.addWidget(self._stats_lbl)

        self.canvas = FigureCanvasQTAgg(self.figure)
        _scroll(self.canvas)
        tb = NavigationToolbar2QT(self.canvas, self)
        tb.setStyleSheet("background-color: #0f3460;")
        layout.addWidget(tb)
        layout.addWidget(self.canvas)

    def set_session(self, s: "SessionAnalysis"):
        self.session = s
        self._update()

    def _update(self):
        if not self.session:
            return
        lap = self.session.best_lap
        result = estimate_energy(
            lap.time, lap.speed,
            mass_kg=self._mass.value(),
            battery_capacity_kwh=self._cap.value(),
            regen_efficiency=self._regen.value(),
        )
        self._stats_lbl.setText(
            f"Motor draw:  {result.total_kwh*1000:.0f} Wh/lap   |   "
            f"Regen recover:  {result.regen_kwh*1000:.0f} Wh/lap   |   "
            f"Net consumption:  {result.net_kwh*1000:.0f} Wh/lap\n"
            f"Avg power:   {result.avg_power_kw:.2f} kW   |   "
            f"Peak power:  {result.peak_power_kw:.1f} kW   |   "
            f"Laps per charge:  {result.laps_per_charge:.1f}   |   "
            f"Est. range:  {result.estimated_range_km:.1f} km"
        )

        # Power trace
        dt = np.diff(lap.time, prepend=lap.time[0])
        dt[0] = dt[1] if len(dt) > 1 else 0.04
        from scipy.ndimage import gaussian_filter1d
        smooth = gaussian_filter1d(lap.speed, sigma=5)
        accel = np.gradient(smooth, lap.time)
        g = 9.81; rho = 1.225
        mass = self._mass.value()
        F = mass * accel + 0.5 * rho * 0.8 * 0.6 * smooth**2 + mass * g * 0.018
        P_kw = F * smooth / 1000.0

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        _style(ax)
        ax.fill_between(lap.time, P_kw, 0,
                        where=(P_kw >= 0), color="#00FF88", alpha=0.5, label="Motor power")
        ax.fill_between(lap.time, P_kw, 0,
                        where=(P_kw < 0),  color="#00BFFF", alpha=0.5, label="Regen / coasting")
        ax.plot(lap.time, P_kw, color="#FFFFFF", linewidth=0.7, alpha=0.4)
        ax.set_xlabel("Time (s)", color="#aaaacc")
        ax.set_ylabel("Power (kW)", color="#aaaacc")
        ax.set_title("Estimated Power Trace — Best Lap", color="#e0e0e0", fontsize=10)
        ax.axhline(0, color="#555577", linewidth=0.8)
        ax.legend(facecolor="#0d1b2a", edgecolor="#333355",
                  labelcolor="#e0e0e0", fontsize=8)
        self.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Main Tab
# ---------------------------------------------------------------------------

class TelemetryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._map   = _TrackMapTab()
        self._delta = _DeltaTab()
        self._energy= _EnergyTab()

        self._tabs.addTab(self._map,    "Track Map")
        self._tabs.addTab(self._delta,  "Lap Delta (Distance)")
        self._tabs.addTab(self._energy, "Energy Analysis")
        layout.addWidget(self._tabs)

    def set_session(self, analysis: "SessionAnalysis"):
        self._map.set_session(analysis)
        self._delta.set_session(analysis)
        self._energy.set_session(analysis)
