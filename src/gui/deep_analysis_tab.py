"""
Deep Analysis Tab — professional race-engineer view.

Sub-tabs:
  • Speed vs Distance  – overlaid laps on distance axis (more useful than time axis)
  • Sector Analysis    – sector splits, theoretical best lap, per-sector bar chart
  • Corner Consistency – apex/entry/exit speed scatter across all laps per corner
  • Driver Metrics     – smoothness score, throttle-on time, theoretical gap
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTabWidget, QCheckBox, QSizePolicy, QSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QSplitter, QGroupBox, QGridLayout,
)
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from src.deep_analysis import (
    speed_vs_distance, sector_splits, theoretical_best_lap,
    corner_consistency_across_laps, estimate_energy, driver_smoothness_score,
)

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis

CHART_BG = "#0d1b2a"
GRID_C   = "#1a2a3a"
LAP_PALETTE = [
    "#00BFFF", "#FF6B6B", "#00FF88", "#FFD700", "#FF8800",
    "#CC88FF", "#FF88CC", "#88FFCC", "#FFAA44", "#44AAFF",
]


def _style(ax):
    ax.set_facecolor(CHART_BG)
    ax.tick_params(colors="#aaaacc", labelsize=8)
    ax.xaxis.label.set_color("#aaaacc")
    ax.yaxis.label.set_color("#aaaacc")
    for sp in ax.spines.values():
        sp.set_edgecolor("#333355")
    ax.grid(True, color=GRID_C, linewidth=0.5, linestyle="--")


def _scroll_zoom(canvas):
    def _handler(event):
        if event.inaxes is None:
            return
        scale = 0.85 if event.button == "up" else 1.15
        ax = event.inaxes
        xd, yd = event.xdata, event.ydata
        ax.set_xlim([xd + (x - xd) * scale for x in ax.get_xlim()])
        ax.set_ylim([yd + (y - yd) * scale for y in ax.get_ylim()])
        canvas.draw_idle()
    canvas.mpl_connect("scroll_event", _handler)


# ---------------------------------------------------------------------------
# Speed vs Distance sub-tab
# ---------------------------------------------------------------------------

class _SvDTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self.figure = Figure(facecolor=CHART_BG)
        layout = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Show:"))
        self._mode = QComboBox()
        self._mode.addItems(["Best lap only", "All laps", "Best + worst"])
        self._mode.currentIndexChanged.connect(self._plot)
        ctrl.addWidget(self._mode)
        ctrl.addSpacing(20)
        self._show_corners = QCheckBox("Corner markers")
        self._show_corners.setChecked(True)
        self._show_corners.toggled.connect(self._plot)
        ctrl.addWidget(self._show_corners)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self.canvas = FigureCanvasQTAgg(self.figure)
        _scroll_zoom(self.canvas)
        tb = NavigationToolbar2QT(self.canvas, self)
        tb.setStyleSheet("background-color: #0f3460;")
        layout.addWidget(tb)
        layout.addWidget(self.canvas)

    def set_session(self, s: "SessionAnalysis"):
        self.session = s
        self._plot()

    def _plot(self):
        if not self.session:
            return
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        _style(ax)
        ax.set_xlabel("Distance (m)")
        ax.set_ylabel("Speed (km/h)")
        ax.set_title("Speed vs Distance", color="#e0e0e0", fontsize=10)

        mode = self._mode.currentText()
        laps = self.session.laps
        best_idx = self.session.best_lap_index

        if mode == "Best lap only":
            show_laps = [(best_idx, laps[best_idx])]
        elif mode == "Best + worst":
            worst_idx = int(np.argmax([l.lap_time for l in laps]))
            show_laps = [(best_idx, laps[best_idx]), (worst_idx, laps[worst_idx])]
        else:
            show_laps = list(enumerate(laps))

        for i, (li, lap) in enumerate(show_laps):
            dist = speed_vs_distance(lap.time, lap.speed)
            color = LAP_PALETTE[i % len(LAP_PALETTE)]
            lw = 2.2 if li == best_idx else 1.0
            alpha = 0.95 if li == best_idx else 0.55
            ax.plot(dist, lap.speed * 3.6, color=color, linewidth=lw,
                    alpha=alpha, label=f"Lap {lap.lap_number} ({lap.lap_time_str})")

            if self._show_corners.isChecked() and li == best_idx:
                for c in lap.corners:
                    apex_dist = float(np.interp(c.apex_time, lap.time, dist))
                    ax.axvline(apex_dist, color="#FFD700", linewidth=0.6,
                               alpha=0.5, linestyle=":")
                    ax.text(apex_dist, ax.get_ylim()[0] if ax.get_ylim()[0] != 0 else 1,
                            f"C{c.corner_number}", color="#FFD700", fontsize=7,
                            ha="center", va="bottom",
                            transform=ax.get_xaxis_transform())

        ax.legend(facecolor="#0d1b2a", edgecolor="#333355",
                  labelcolor="#e0e0e0", fontsize=8)
        self.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Sector Analysis sub-tab
# ---------------------------------------------------------------------------

class _SectorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self.figure = Figure(facecolor=CHART_BG)
        layout = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Sectors:"))
        self._n_sectors = QSpinBox()
        self._n_sectors.setRange(3, 10)
        self._n_sectors.setValue(5)
        self._n_sectors.valueChanged.connect(self._update)
        ctrl.addWidget(self._n_sectors)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        splitter = QSplitter(Qt.Horizontal)

        # Chart
        chart_w = QWidget()
        chart_l = QVBoxLayout(chart_w)
        self.canvas = FigureCanvasQTAgg(self.figure)
        _scroll_zoom(self.canvas)
        tb = NavigationToolbar2QT(self.canvas, self)
        tb.setStyleSheet("background-color: #0f3460;")
        chart_l.addWidget(tb)
        chart_l.addWidget(self.canvas)
        splitter.addWidget(chart_w)

        # Summary panel
        summary_w = QGroupBox("Theoretical Best Lap")
        summary_l = QVBoxLayout(summary_w)
        self._theo_lbl = QLabel("Load session to compute")
        self._theo_lbl.setStyleSheet("font-size: 14px; color: #00FF88; padding: 6px;")
        self._theo_lbl.setWordWrap(True)
        summary_l.addWidget(self._theo_lbl)
        self._sector_table = QTableWidget()
        self._sector_table.setColumnCount(4)
        self._sector_table.setHorizontalHeaderLabels(
            ["Sector", "Best Time", "Best Lap #", "Saving vs Actual"]
        )
        self._sector_table.setEditTriggers(QTableWidget.NoEditTriggers)
        summary_l.addWidget(self._sector_table)
        splitter.addWidget(summary_w)
        splitter.setSizes([700, 350])

        layout.addWidget(splitter)

    def set_session(self, s: "SessionAnalysis"):
        self.session = s
        self._update()

    def _update(self):
        if not self.session:
            return
        ns = self._n_sectors.value()
        laps = self.session.laps
        best = self.session.best_lap
        best_sectors = sector_splits(best, ns)
        theo_time, theo_sectors, theo_lap_idxs = theoretical_best_lap(self.session, ns)
        actual_best = best.lap_time

        # Headline
        gap = actual_best - theo_time
        self._theo_lbl.setText(
            f"Theoretical Best: {self._fmt(theo_time)}\n"
            f"Actual Best: {self._fmt(actual_best)}\n"
            f"Gap to perfect: {gap:.3f}s"
        )

        # Sector table
        self._sector_table.setRowCount(len(theo_sectors))
        for row, (theo_t, lap_i, act_s) in enumerate(
                zip(theo_sectors, theo_lap_idxs, best_sectors)):
            saving = act_s.time_s - theo_t
            items = [
                f"S{row+1}",
                f"{theo_t:.3f}s",
                f"Lap {laps[lap_i].lap_number if lap_i < len(laps) else '?'}",
                f"-{saving:.3f}s" if saving > 0 else "= best",
            ]
            for col, txt in enumerate(items):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignCenter)
                if saving > 0.05 and col == 3:
                    from PyQt5.QtGui import QColor
                    item.setForeground(QColor("#FFD700"))
                self._sector_table.setItem(row, col, item)
        self._sector_table.resizeColumnsToContents()

        # Bar chart: sector times for every lap
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        _style(ax)

        x = np.arange(ns)
        width = 0.8 / max(len(laps), 1)
        for li, lap in enumerate(laps):
            sects = sector_splits(lap, ns)
            if len(sects) != ns:
                continue
            times = [s.time_s for s in sects]
            color = "#e94560" if li == self.session.best_lap_index else LAP_PALETTE[li % len(LAP_PALETTE)]
            alpha = 0.9 if li == self.session.best_lap_index else 0.5
            ax.bar(x + li * width, times, width,
                   label=f"L{lap.lap_number}", color=color, alpha=alpha)

        if theo_sectors:
            ax.bar(x + len(laps) * width, theo_sectors, width,
                   label="Theoretical Best", color="#00FF88", alpha=0.85,
                   edgecolor="#FFFFFF", linewidth=0.5)

        ax.set_xticks(x + width * len(laps) / 2)
        ax.set_xticklabels([f"S{i+1}" for i in range(ns)], color="#aaaacc")
        ax.set_ylabel("Time (s)", color="#aaaacc")
        ax.set_title("Sector Times", color="#e0e0e0", fontsize=10)
        ax.legend(facecolor="#0d1b2a", edgecolor="#333355", labelcolor="#e0e0e0", fontsize=7)
        self.canvas.draw_idle()

    @staticmethod
    def _fmt(t):
        m = int(t // 60); s = t % 60
        return f"{m}:{s:06.3f}"


# ---------------------------------------------------------------------------
# Corner Consistency sub-tab
# ---------------------------------------------------------------------------

class _CornerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self.figure = Figure(facecolor=CHART_BG)
        layout = QVBoxLayout(self)

        self.canvas = FigureCanvasQTAgg(self.figure)
        _scroll_zoom(self.canvas)
        tb = NavigationToolbar2QT(self.canvas, self)
        tb.setStyleSheet("background-color: #0f3460;")
        layout.addWidget(tb)
        layout.addWidget(self.canvas)

    def set_session(self, s: "SessionAnalysis"):
        self.session = s
        self._plot()

    def _plot(self):
        if not self.session:
            return
        stats = corner_consistency_across_laps(self.session)
        if not stats:
            return
        self.figure.clear()
        gs = self.figure.add_gridspec(2, 1, hspace=0.45)
        ax_apex  = self.figure.add_subplot(gs[0])
        ax_score = self.figure.add_subplot(gs[1])

        for ax in (ax_apex, ax_score):
            _style(ax)

        # Box plot of apex speeds per corner
        data = [s.apex_speeds_kmh for s in stats]
        labels = [f"C{s.corner_number}" for s in stats]
        bp = ax_apex.boxplot(data, labels=labels, patch_artist=True,
                             medianprops={"color": "#FFD700", "linewidth": 2},
                             whiskerprops={"color": "#aaaacc"},
                             capprops={"color": "#aaaacc"},
                             flierprops={"marker": "o", "color": "#FF4444",
                                         "markersize": 4})
        for patch in bp["boxes"]:
            patch.set_facecolor("#0f3460")
            patch.set_alpha(0.7)

        ax_apex.set_ylabel("Apex Speed (km/h)", color="#aaaacc")
        ax_apex.set_title("Corner Apex Speed Distribution Across Laps",
                           color="#e0e0e0", fontsize=10)

        # Consistency score bars
        scores = [s.consistency_pct for s in stats]
        colors = ["#00FF88" if sc >= 95 else "#FFD700" if sc >= 85 else "#FF4444"
                  for sc in scores]
        ax_score.bar(labels, scores, color=colors, alpha=0.85)
        ax_score.axhline(95, color="#00FF88", linewidth=1, linestyle="--",
                         alpha=0.7, label="95% target")
        ax_score.set_ylim(50, 105)
        ax_score.set_ylabel("Consistency (%)", color="#aaaacc")
        ax_score.set_title("Corner Consistency Score (100% = identical every lap)",
                           color="#e0e0e0", fontsize=10)
        ax_score.legend(facecolor="#0d1b2a", edgecolor="#333355",
                        labelcolor="#e0e0e0", fontsize=8)

        self.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Driver Metrics sub-tab
# ---------------------------------------------------------------------------

class _DriverTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        layout = QVBoxLayout(self)

        self._grid = QGroupBox("Best Lap Metrics")
        grid_l = QGridLayout(self._grid)
        self._metrics: dict[str, QLabel] = {}
        for row, key in enumerate([
            "Lap Time", "Top Speed", "Avg Speed",
            "Smoothness Score", "% Time Accelerating",
            "% Time Braking", "% Time Cornering",
            "Corners", "Best Apex Speed", "Worst Apex Speed",
        ]):
            k_lbl = QLabel(key + ":")
            k_lbl.setStyleSheet("color: #8888aa;")
            v_lbl = QLabel("—")
            v_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #e0e0e0;")
            grid_l.addWidget(k_lbl, row, 0)
            grid_l.addWidget(v_lbl, row, 1)
            self._metrics[key] = v_lbl
        layout.addWidget(self._grid)
        layout.addStretch()

    def set_session(self, s: "SessionAnalysis"):
        self.session = s
        lap = s.best_lap
        phase = lap.phase
        total = max(len(phase), 1)
        apexes = [c.apex_speed_kmh for c in lap.corners] if lap.corners else [0]
        smooth = driver_smoothness_score(lap.time, lap.speed)

        data = {
            "Lap Time":              lap.lap_time_str,
            "Top Speed":             f"{lap.max_speed_kmh:.1f} km/h",
            "Avg Speed":             f"{lap.avg_speed_kmh:.1f} km/h",
            "Smoothness Score":      f"{smooth:.1f} / 100",
            "% Time Accelerating":   f"{(phase=='accelerating').sum()/total*100:.1f}%",
            "% Time Braking":        f"{(phase=='braking').sum()/total*100:.1f}%",
            "% Time Cornering":      f"{(phase=='cornering').sum()/total*100:.1f}%",
            "Corners":               str(len(lap.corners)),
            "Best Apex Speed":       f"{max(apexes):.1f} km/h" if apexes else "—",
            "Worst Apex Speed":      f"{min(apexes):.1f} km/h" if apexes else "—",
        }
        for key, val in data.items():
            if key in self._metrics:
                self._metrics[key].setText(val)
                if key == "Smoothness Score":
                    color = "#00FF88" if smooth >= 70 else "#FFD700" if smooth >= 50 else "#FF4444"
                    self._metrics[key].setStyleSheet(
                        f"font-size: 13px; font-weight: bold; color: {color};"
                    )


# ---------------------------------------------------------------------------
# Main Tab
# ---------------------------------------------------------------------------

class DeepAnalysisTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        hdr = QLabel("Deep Analysis")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #e94560; padding: 2px 0;")
        layout.addWidget(hdr)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._svd   = _SvDTab()
        self._sec   = _SectorTab()
        self._corn  = _CornerTab()
        self._drv   = _DriverTab()

        self._tabs.addTab(self._svd,  "Speed vs Distance")
        self._tabs.addTab(self._sec,  "Sector Analysis")
        self._tabs.addTab(self._corn, "Corner Consistency")
        self._tabs.addTab(self._drv,  "Driver Metrics")

        layout.addWidget(self._tabs)

    def set_session(self, analysis: "SessionAnalysis"):
        self._svd.set_session(analysis)
        self._sec.set_session(analysis)
        self._corn.set_session(analysis)
        self._drv.set_session(analysis)
