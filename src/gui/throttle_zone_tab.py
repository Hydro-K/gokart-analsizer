"""Throttle zone breakdown: % time in accelerating / braking / cornering / straight."""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
)
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec

CHART_BG = "#0d1b2a"
PHASE_COLORS = {
    "accelerating": "#00FF88",
    "braking":      "#FF4444",
    "cornering":    "#FFD700",
    "straight":     "#4488FF",
}

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis


class ThrottleZoneTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self.figure = Figure(facecolor=CHART_BG)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        toolbar.setStyleSheet("background-color: #0f3460; color: #e0e0e0;")
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)

    def set_session(self, analysis: "SessionAnalysis") -> None:
        self.session = analysis
        self._replot()

    def _compute_zone_pcts(self, analysis: "SessionAnalysis") -> dict:
        results = {}
        for lap in analysis.laps:
            phase = lap.phase
            total = len(phase)
            counts = {p: 0 for p in PHASE_COLORS}
            for p in phase:
                if p in counts:
                    counts[p] += 1
            results[lap.lap_number] = {p: c / total * 100 for p, c in counts.items()}
        return results

    def _replot(self) -> None:
        if self.session is None:
            return
        self.figure.clear()
        gs = GridSpec(1, 2, figure=self.figure, wspace=0.4)
        ax_pie = self.figure.add_subplot(gs[0, 0])
        ax_bar = self.figure.add_subplot(gs[0, 1])

        for ax in (ax_pie, ax_bar):
            ax.set_facecolor(CHART_BG)
            ax.tick_params(colors="#aaaacc", labelsize=9)
            for spine in ax.spines.values():
                spine.set_edgecolor("#333355")

        # Pie for best lap
        best = self.session.best_lap
        total = len(best.phase)
        pcts = {p: (best.phase == p).sum() / total * 100 for p in PHASE_COLORS}
        labels = [f"{p.capitalize()}\n{pcts[p]:.1f}%" for p in PHASE_COLORS]
        colors = list(PHASE_COLORS.values())
        wedges, _ = ax_pie.pie(
            [pcts[p] for p in PHASE_COLORS],
            labels=None,
            colors=colors,
            startangle=140,
            wedgeprops={"linewidth": 1, "edgecolor": CHART_BG},
        )
        ax_pie.legend(wedges, labels, loc="center left", bbox_to_anchor=(-0.6, 0.5),
                      facecolor="#0d1b2a", edgecolor="#333355", labelcolor="#e0e0e0",
                      fontsize=9)
        ax_pie.set_title(f"Best Lap #{best.lap_number}", color="#e0e0e0", fontsize=10)

        # Stacked bar for all laps
        zone_data = self._compute_zone_pcts(self.session)
        lap_nums = sorted(zone_data.keys())
        bottom = np.zeros(len(lap_nums))
        x = np.arange(len(lap_nums))
        for phase, color in PHASE_COLORS.items():
            vals = [zone_data[n][phase] for n in lap_nums]
            ax_bar.bar(x, vals, bottom=bottom, label=phase.capitalize(),
                       color=color, alpha=0.85)
            bottom += np.array(vals)

        ax_bar.set_xticks(x)
        ax_bar.set_xticklabels([f"L{n}" for n in lap_nums], color="#aaaacc", fontsize=8)
        ax_bar.set_ylabel("% of Lap Time", color="#aaaacc")
        ax_bar.set_ylim(0, 105)
        ax_bar.yaxis.label.set_color("#aaaacc")
        ax_bar.set_title("All Laps — Zone Breakdown", color="#e0e0e0", fontsize=10)
        ax_bar.grid(True, color="#1a2a3a", linewidth=0.5, linestyle="--", axis="y")
        ax_bar.legend(facecolor="#0d1b2a", edgecolor="#333355", labelcolor="#e0e0e0",
                      fontsize=8)

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
