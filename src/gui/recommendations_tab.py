"""Recommendations tab: card-based display with Apply All button."""

from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal

if TYPE_CHECKING:
    from src.recommendations import Recommendation

PRIORITY_COLORS = {1: "#FF4444", 2: "#FFD700", 3: "#00FF88"}
PRIORITY_LABELS = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}
CATEGORY_ICONS = {
    "Alltrax": "⚡",
    "Gear Ratio": "⚙",
    "Throttle Curve": "〰",
    "Driver": "🏎",
}


class _RecCard(QFrame):
    def __init__(self, rec: "Recommendation", parent=None):
        super().__init__(parent)
        color = PRIORITY_COLORS.get(rec.priority, "#888888")
        self.setStyleSheet(
            f"QFrame {{ border: 1px solid {color}; border-radius: 8px; "
            f"background-color: #0d1b2a; padding: 4px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        icon = CATEGORY_ICONS.get(rec.category, "•")
        header = QHBoxLayout()
        title = QLabel(f"{icon}  [{rec.category}]  {rec.parameter}")
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")
        header.addWidget(title)
        pri_badge = QLabel(PRIORITY_LABELS.get(rec.priority, ""))
        pri_badge.setStyleSheet(
            f"background-color: {color}; color: #000000; font-size: 10px; "
            f"font-weight: bold; padding: 2px 6px; border-radius: 4px;"
        )
        header.addStretch()
        header.addWidget(pri_badge)
        layout.addLayout(header)

        change_row = QHBoxLayout()
        change_row.addWidget(QLabel(f"Current:"))
        curr = QLabel(rec.current_value)
        curr.setStyleSheet("color: #FF8866; font-weight: bold;")
        change_row.addWidget(curr)
        change_row.addWidget(QLabel("→"))
        recom = QLabel(rec.recommended_value)
        recom.setStyleSheet("color: #00FF88; font-weight: bold;")
        change_row.addWidget(recom)
        change_row.addStretch()
        layout.addLayout(change_row)

        reason = QLabel(rec.reason)
        reason.setWordWrap(True)
        reason.setStyleSheet("color: #aaaacc; font-size: 11px;")
        layout.addWidget(reason)


class RecommendationsTab(QWidget):
    apply_all_clicked = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recs: List["Recommendation"] = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QHBoxLayout()
        self._count_label = QLabel("No recommendations yet. Load a session first.")
        self._count_label.setStyleSheet("color: #8888aa; font-size: 13px;")
        header.addWidget(self._count_label)
        header.addStretch()

        self._apply_btn = QPushButton("Apply All Recommendations")
        self._apply_btn.setStyleSheet(
            "background-color: #e94560; font-weight: bold; padding: 6px 16px;"
        )
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        header.addWidget(self._apply_btn)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()
        scroll.setWidget(self._cards_widget)
        layout.addWidget(scroll)

    def set_recommendations(self, recs: List["Recommendation"]):
        self._recs = recs
        # Clear old cards
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not recs:
            placeholder = QLabel("No recommendations. Data looks good!")
            placeholder.setStyleSheet("color: #00FF88; font-size: 14px; padding: 20px;")
            placeholder.setAlignment(Qt.AlignCenter)
            self._cards_layout.insertWidget(0, placeholder)
            self._count_label.setText("No recommendations")
            self._apply_btn.setEnabled(False)
            return

        for i, rec in enumerate(recs):
            card = _RecCard(rec)
            self._cards_layout.insertWidget(i, card)

        actionable = [r for r in recs if r.setting_key and r.delta != 0]
        self._count_label.setText(
            f"{len(recs)} recommendation(s)  |  {len(actionable)} auto-applicable"
        )
        self._apply_btn.setEnabled(bool(actionable))

    def _on_apply(self):
        self.apply_all_clicked.emit(self._recs)
