"""Corner analysis tab: entry / apex / exit speeds per corner."""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QSplitter, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

CHART_BG = "#0d1b2a"
GRID_COLOR = "#1a2a3a"

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis


class CornerTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self.figure = Figure(facecolor=CHART_BG)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Vertical)

        # Chart
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        self.ax = self.figure.add_subplot(111)
        self._style_axes()
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        toolbar.setStyleSheet("background-color: #0f3460; color: #e0e0e0;")
        chart_layout.addWidget(toolbar)
        chart_layout.addWidget(self.canvas)
        splitter.addWidget(chart_widget)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Corner", "Entry (km/h)", "Apex (km/h)", "Exit (km/h)",
            "Entry Time (s)", "Apex Time (s)", "Exit Time (s)"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.table)

        splitter.setSizes([600, 250])
        layout.addWidget(splitter)

    def _style_axes(self) -> None:
        ax = self.ax
        ax.set_facecolor(CHART_BG)
        ax.tick_params(colors="#aaaacc", labelsize=9)
        ax.xaxis.label.set_color("#aaaacc")
        ax.yaxis.label.set_color("#aaaacc")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--")
        ax.set_xlabel("Corner #")
        ax.set_ylabel("Speed (km/h)")

    def set_session(self, analysis: "SessionAnalysis") -> None:
        self.session = analysis
        self._replot()

    def _replot(self) -> None:
        if self.session is None:
            return
        lap = self.session.best_lap
        corners = lap.corners
        if not corners:
            self.ax.cla()
            self._style_axes()
            self.ax.text(
                0.5, 0.5, "No corners detected",
                ha="center", va="center", color="#888888",
                transform=self.ax.transAxes,
            )
            self.canvas.draw_idle()
            return

        nums = [c.corner_number for c in corners]
        entries = [c.entry_speed_kmh for c in corners]
        apexes = [c.apex_speed_kmh for c in corners]
        exits = [c.exit_speed_kmh for c in corners]

        x = np.arange(len(nums))
        w = 0.25

        self.ax.cla()
        self._style_axes()
        self.ax.bar(x - w, entries, w, label="Entry", color="#4488FF", alpha=0.85)
        self.ax.bar(x,      apexes, w, label="Apex",  color="#FFD700", alpha=0.85)
        self.ax.bar(x + w,  exits,  w, label="Exit",  color="#00FF88", alpha=0.85)

        self.ax.set_xticks(x)
        self.ax.set_xticklabels([f"C{n}" for n in nums], color="#aaaacc")
        self.ax.legend(facecolor="#0d1b2a", edgecolor="#333355", labelcolor="#e0e0e0")
        self.ax.set_title(
            f"Corner Speeds — Best Lap #{lap.lap_number}",
            color="#e0e0e0", fontsize=11, pad=8,
        )
        self.canvas.draw_idle()

        # Table
        self.table.setRowCount(len(corners))
        for row, c in enumerate(corners):
            for col, val in enumerate([
                str(c.corner_number),
                f"{c.entry_speed_kmh:.1f}",
                f"{c.apex_speed_kmh:.1f}",
                f"{c.exit_speed_kmh:.1f}",
                f"{c.entry_time:.2f}",
                f"{c.apex_time:.2f}",
                f"{c.exit_time:.2f}",
            ]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()

    def _on_scroll(self, event) -> None:
        if event.inaxes is None:
            return
        scale = 0.85 if event.button == "up" else 1.15
        ax = event.inaxes
        xd, yd = event.xdata, event.ydata
        ax.set_xlim([xd + (x - xd) * scale for x in ax.get_xlim()])
        ax.set_ylim([yd + (y - yd) * scale for y in ax.get_ylim()])
        self.canvas.draw_idle()
