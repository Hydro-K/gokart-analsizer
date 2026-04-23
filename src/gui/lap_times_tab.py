"""Lap times table with statistics."""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QGroupBox, QGridLayout,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis


def _fmt_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:06.3f}"


class LapTimesTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        # Stats row
        self.stats_group = QGroupBox("Session Statistics")
        stats_layout = QGridLayout(self.stats_group)
        self._stat_labels: dict[str, QLabel] = {}
        for col, key in enumerate(["Best Lap", "Avg Lap", "Std Dev", "Consistency", "Total Laps"]):
            title = QLabel(key)
            title.setStyleSheet("color: #8888aa; font-size: 11px;")
            title.setAlignment(Qt.AlignCenter)
            value = QLabel("—")
            value.setStyleSheet("font-size: 18px; font-weight: bold; color: #e94560;")
            value.setAlignment(Qt.AlignCenter)
            stats_layout.addWidget(title, 0, col)
            stats_layout.addWidget(value, 1, col)
            self._stat_labels[key] = value
        layout.addWidget(self.stats_group)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Lap", "Lap Time", "Delta (Best)", "Max Speed", "Avg Speed", "Corners"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

    def set_session(self, analysis: "SessionAnalysis") -> None:
        self.session = analysis
        self._populate(analysis)

    def _populate(self, analysis: "SessionAnalysis") -> None:
        best_time = analysis.best_lap.lap_time
        self._stat_labels["Best Lap"].setText(_fmt_time(best_time))
        self._stat_labels["Avg Lap"].setText(_fmt_time(analysis.avg_lap_time))
        self._stat_labels["Std Dev"].setText(f"{analysis.std_lap_time:.3f}s")
        self._stat_labels["Consistency"].setText(f"{analysis.consistency_pct:.1f}%")
        self._stat_labels["Total Laps"].setText(str(len(analysis.laps)))

        self.table.setRowCount(len(analysis.laps))
        for row, lap in enumerate(analysis.laps):
            delta = lap.lap_time - best_time
            is_best = row == analysis.best_lap_index

            def cell(text: str, align=Qt.AlignCenter) -> QTableWidgetItem:
                item = QTableWidgetItem(text)
                item.setTextAlignment(align)
                if is_best:
                    item.setForeground(QColor("#FFD700"))
                    item.setBackground(QColor("#1a2a10"))
                return item

            self.table.setItem(row, 0, cell(f"{'★ ' if is_best else ''}{lap.lap_number}"))
            self.table.setItem(row, 1, cell(_fmt_time(lap.lap_time)))
            delta_str = ("BEST" if is_best else f"+{delta:.3f}s")
            d_item = cell(delta_str)
            if not is_best:
                d_item.setForeground(QColor("#FF8866" if delta > 1 else "#FFCC66"))
            self.table.setItem(row, 2, d_item)
            self.table.setItem(row, 3, cell(f"{lap.max_speed_kmh:.1f} km/h"))
            self.table.setItem(row, 4, cell(f"{lap.avg_speed_kmh:.1f} km/h"))
            self.table.setItem(row, 5, cell(str(len(lap.corners))))

        self.table.resizeColumnsToContents()
