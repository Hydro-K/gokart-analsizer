"""Session setup tab: file loading, driver names, session overview."""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QLineEdit, QFileDialog, QGridLayout, QFrame,
)
from PyQt5.QtCore import pyqtSignal, Qt

if TYPE_CHECKING:
    from src.data_loader import RawSessionData
    from src.lap_analyzer import SessionAnalysis


class _DriverPanel(QGroupBox):
    load_requested = pyqtSignal(str, str)  # filepath, driver_name

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._filepath = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        # Driver name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Driver name:"))
        self.name_edit = QLineEdit(self.title().replace("Driver ", "Driver "))
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # File picker
        file_row = QHBoxLayout()
        self.file_label = QLabel("No file loaded")
        self.file_label.setWordWrap(True)
        self.browse_btn = QPushButton("Browse CSV…")
        self.browse_btn.clicked.connect(self._browse)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(self.browse_btn)
        layout.addLayout(file_row)

        # Load button
        self.load_btn = QPushButton("Load Session")
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._emit_load)
        layout.addWidget(self.load_btn)

        # Info grid
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #333366;")
        layout.addWidget(sep)

        self.info_grid = QGridLayout()
        self._info_labels: dict[str, QLabel] = {}
        for row, key in enumerate(["Filename", "Laps", "Best Lap", "Avg Lap", "Consistency", "Sample Rate"]):
            k_lbl = QLabel(key + ":")
            k_lbl.setStyleSheet("color: #8888aa;")
            v_lbl = QLabel("—")
            self.info_grid.addWidget(k_lbl, row, 0)
            self.info_grid.addWidget(v_lbl, row, 1)
            self._info_labels[key] = v_lbl
        layout.addLayout(self.info_grid)
        layout.addStretch()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open AiM Solo 2 CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if path:
            self._filepath = path
            self.file_label.setText(path.split("/")[-1])
            self.load_btn.setEnabled(True)

    def _emit_load(self) -> None:
        if self._filepath:
            self.load_requested.emit(self._filepath, self.name_edit.text().strip() or self.title())

    def update_info(self, raw: "RawSessionData", analysis: "SessionAnalysis") -> None:
        self._info_labels["Filename"].setText(raw.filename)
        self._info_labels["Laps"].setText(str(len(analysis.laps)))
        self._info_labels["Best Lap"].setText(analysis.best_lap.lap_time_str)
        self._info_labels["Avg Lap"].setText(
            f"{analysis.avg_lap_time:.3f}s ({int(analysis.avg_lap_time // 60)}:{analysis.avg_lap_time % 60:06.3f})"
        )
        self._info_labels["Consistency"].setText(f"{analysis.consistency_pct:.1f}%")
        self._info_labels["Sample Rate"].setText(f"{raw.sample_rate:.0f} Hz")


class SessionTab(QWidget):
    load_session1_requested = pyqtSignal(str, str)
    load_session2_requested = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("EV Kart Data Analyzer")
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #e94560; padding: 10px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        sub = QLabel("Purdue EV Grand Prix  ·  AiM Solo 2  ·  Alltrax SR-72400")
        sub.setStyleSheet("font-size: 12px; color: #8888aa; padding-bottom: 16px;")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        # Driver panels
        panels_row = QHBoxLayout()

        self.driver1_panel = _DriverPanel("Driver 1")
        self.driver1_panel.load_requested.connect(self.load_session1_requested)
        panels_row.addWidget(self.driver1_panel)

        self.driver2_panel = _DriverPanel("Driver 2  (optional comparison)")
        self.driver2_panel.load_requested.connect(self.load_session2_requested)
        panels_row.addWidget(self.driver2_panel)

        layout.addLayout(panels_row)

        # Instructions
        instr = QLabel(
            "Instructions:\n"
            "1. Export your AiM Solo 2 session as CSV from AiM Race Studio 3.\n"
            "2. Browse to the file above and click Load Session.\n"
            "3. Optionally load a second driver's CSV for comparison.\n"
            "4. Navigate the tabs to explore lap data, speed traces, and corners.\n"
            "5. Open the Settings tab to edit Alltrax parameters and see real-time projections.\n"
            "6. Apply recommendations with one click, then export your setup log."
        )
        instr.setStyleSheet(
            "background-color: #0d1b2a; border: 1px solid #333366; "
            "border-radius: 6px; padding: 14px; color: #aaaacc; line-height: 1.6;"
        )
        instr.setWordWrap(True)
        layout.addWidget(instr)
        layout.addStretch()

    def update_session1_info(self, raw: "RawSessionData", analysis: "SessionAnalysis") -> None:
        self.driver1_panel.update_info(raw, analysis)

    def update_session2_info(self, raw: "RawSessionData", analysis: "SessionAnalysis") -> None:
        self.driver2_panel.update_info(raw, analysis)
