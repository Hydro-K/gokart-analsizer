"""Setup log tab: change history table + session notes."""

from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QTextEdit, QGroupBox, QSplitter,
)
from PyQt5.QtCore import Qt

from src.setup_log import SetupLog


class SetupLogTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._log: SetupLog = parent.setup_log if hasattr(parent, "setup_log") else SetupLog()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Vertical)

        # Table
        table_group = QGroupBox("Parameter Changes")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Parameter", "Old Value", "New Value"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        table_layout.addWidget(self.table)
        splitter.addWidget(table_group)

        # Notes
        notes_group = QGroupBox("Session Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "Add notes about this session: track conditions, driver feedback, issues observed…"
        )
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        notes_layout.addWidget(self.notes_edit)
        splitter.addWidget(notes_group)

        splitter.setSizes([400, 200])
        layout.addWidget(splitter)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Log")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)

        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def refresh(self):
        entries = self._log.entries
        self.table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            for col, val in enumerate([e.timestamp, e.parameter, e.old_value, e.new_value]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        if self._log.session_notes and not self.notes_edit.toPlainText():
            self.notes_edit.setPlainText(self._log.session_notes)

    def _on_notes_changed(self):
        self._log.session_notes = self.notes_edit.toPlainText()

    def _clear(self):
        self._log.clear()
        self.table.setRowCount(0)
        self.notes_edit.clear()
