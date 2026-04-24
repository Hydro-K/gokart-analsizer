"""
Session tab — file loading, driver names, session overview, and multi-file
SCCA / AiM session management.
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QLineEdit, QFileDialog, QGridLayout, QFrame,
    QListWidget, QListWidgetItem, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QFont

if TYPE_CHECKING:
    from src.data_loader import RawSessionData
    from src.lap_analyzer import SessionAnalysis
    from src.session_manager import SessionManager


# ---------------------------------------------------------------------------
# Single-driver panel (unchanged interface, improved layout)
# ---------------------------------------------------------------------------

class _DriverPanel(QGroupBox):
    load_requested = pyqtSignal(str, str)   # filepath, driver_name

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._filepath = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        # Driver name row
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Driver name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Alex Smith")
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # File picker row
        file_row = QHBoxLayout()
        self.file_label = QLabel("No file loaded")
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("color:#8888aa;")
        self.browse_btn = QPushButton("📂  Browse CSV…")
        self.browse_btn.clicked.connect(self._browse)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(self.browse_btn)
        layout.addLayout(file_row)

        # Load button
        self.load_btn = QPushButton("▶  Load Session")
        self.load_btn.setEnabled(False)
        self.load_btn.setStyleSheet(
            "QPushButton:enabled { background:#0f3460; font-weight:bold; }"
        )
        self.load_btn.clicked.connect(self._emit_load)
        layout.addWidget(self.load_btn)

        # Stats grid
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #333366;")
        layout.addWidget(sep)

        grid = QGridLayout()
        self._info: dict[str, QLabel] = {}
        rows = [
            ("Filename",     "File"),
            ("Laps",         "Laps"),
            ("Best Lap",     "Best Lap"),
            ("Avg Lap",      "Avg Lap"),
            ("Consistency",  "Consistency"),
            ("Sample Rate",  "Sample Rate"),
            ("Top Speed",    "Top Speed"),
        ]
        for row, (key, label) in enumerate(rows):
            k_lbl = QLabel(label + ":")
            k_lbl.setStyleSheet("color:#8888aa; font-size:11px;")
            v_lbl = QLabel("—")
            v_lbl.setStyleSheet("font-size:12px;")
            grid.addWidget(k_lbl, row, 0)
            grid.addWidget(v_lbl, row, 1)
            self._info[key] = v_lbl
        layout.addLayout(grid)
        layout.addStretch()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open AiM Solo 2 / SCCA CSV", "",
            "CSV files (*.csv);;All files (*)"
        )
        if path:
            self._filepath = path
            self.file_label.setText(path.split("/")[-1])
            self.file_label.setStyleSheet("color:#e0e0e0;")
            self.load_btn.setEnabled(True)

    def _emit_load(self) -> None:
        if self._filepath:
            name = self.name_edit.text().strip() or self.title()
            self.load_requested.emit(self._filepath, name)

    def update_info(self, raw: "RawSessionData", analysis: "SessionAnalysis") -> None:
        self._info["Filename"].setText(raw.filename)
        self._info["Laps"].setText(str(len(analysis.laps)))
        self._info["Best Lap"].setText(analysis.best_lap.lap_time_str)
        avg = analysis.avg_lap_time
        self._info["Avg Lap"].setText(
            f"{int(avg//60)}:{avg%60:06.3f}"
        )
        self._info["Consistency"].setText(f"{analysis.consistency_pct:.1f}%")
        self._info["Sample Rate"].setText(f"{raw.sample_rate:.0f} Hz")
        top_kmh = analysis.best_lap.max_speed_kmh
        self._info["Top Speed"].setText(f"{top_kmh:.1f} km/h  ({top_kmh/1.609:.0f} mph)")

        # Colour-code consistency
        c = analysis.consistency_pct
        col = "#00cc66" if c >= 93 else "#FFD700" if c >= 85 else "#ff4444"
        self._info["Consistency"].setStyleSheet(f"color:{col}; font-weight:bold;")


# ---------------------------------------------------------------------------
# Multi-session list panel
# ---------------------------------------------------------------------------

class _SessionListPanel(QGroupBox):
    """Shows all loaded sessions; lets user pick which two to compare."""
    compare_requested = pyqtSignal(int, int)  # idx_a, idx_b

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("All Loaded Sessions", parent)
        self._sessions = []
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Load multiple AiM / SCCA files to compare sessions from the same device.\n"
            "Select two rows, then click 'Compare Selected'."
        )
        info.setStyleSheet("color:#8888aa; font-size:11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["#", "File", "Laps", "Best Lap", "Consistency"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.compare_btn = QPushButton("👥  Compare Selected")
        self.compare_btn.setEnabled(False)
        self.compare_btn.clicked.connect(self._emit_compare)
        btn_row.addWidget(self.compare_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def refresh(self, manager: "SessionManager") -> None:
        self._sessions = list(manager.sessions)
        self.table.setRowCount(0)
        for i, s in enumerate(self._sessions):
            row = self.table.rowCount()
            self.table.insertRow(row)
            a = s.analysis
            cells = [
                str(i + 1),
                s.raw.filename,
                str(len(a.laps)),
                a.best_lap.lap_time_str,
                f"{a.consistency_pct:.1f}%",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(s.color))
                self.table.setItem(row, col, item)
        self.table.resizeRowsToContents()
        self.compare_btn.setEnabled(len(self._sessions) >= 2)

    def _emit_compare(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if len(rows) >= 2:
            self.compare_requested.emit(rows[0], rows[1])
        elif len(self._sessions) >= 2:
            self.compare_requested.emit(0, 1)


# ---------------------------------------------------------------------------
# Main Session Tab
# ---------------------------------------------------------------------------

class SessionTab(QWidget):
    load_session1_requested  = pyqtSignal(str, str)   # filepath, name
    load_session2_requested  = pyqtSignal(str, str)
    load_multiple_requested  = pyqtSignal(list, str)  # [filepaths], name

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ---- Header -------------------------------------------------------
        hdr = QLabel("EV Kart Data Analyzer")
        hdr.setStyleSheet(
            "font-size:24px; font-weight:bold; color:#e94560; padding:8px;"
        )
        hdr.setAlignment(Qt.AlignCenter)
        layout.addWidget(hdr)

        sub = QLabel(
            "Purdue EV Grand Prix  ·  AiM Solo 2  ·  Alltrax SR Controller  ·  Hoosier R60B"
        )
        sub.setStyleSheet("font-size:12px; color:#8888aa; padding-bottom:8px;")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        # ---- Tabs: single load / multi-load -------------------------------
        load_tabs = QTabWidget()
        load_tabs.setMaximumHeight(340)

        # Single-session tab
        single_widget = QWidget()
        single_layout = QHBoxLayout(single_widget)
        self.driver1_panel = _DriverPanel("Driver 1")
        self.driver1_panel.load_requested.connect(self.load_session1_requested)
        self.driver2_panel = _DriverPanel("Driver 2  (optional comparison)")
        self.driver2_panel.load_requested.connect(self.load_session2_requested)
        single_layout.addWidget(self.driver1_panel)
        single_layout.addWidget(self.driver2_panel)
        load_tabs.addTab(single_widget, "📂  Load Single Sessions")

        # Multi-file tab
        multi_widget = self._build_multi_tab()
        load_tabs.addTab(multi_widget, "📂📂  Load Multiple SCCA Files")

        layout.addWidget(load_tabs)

        # ---- Session list (shows after multi-load) ------------------------
        self.session_list_panel = _SessionListPanel()
        self.session_list_panel.setVisible(False)
        layout.addWidget(self.session_list_panel)

        # ---- Quick-start instructions ------------------------------------
        self.instructions = QLabel(
            "Quick start:\n"
            "  1.  Browse to your AiM CSV export and click Load Session.\n"
            "  2.  Or use 'Load Multiple SCCA Files' to load an entire event at once.\n"
            "  3.  Open the ⚙️ Settings tab and import your Alltrax settings (.aep).\n"
            "  4.  Check the 🏁 Rules tab — violations appear in red immediately.\n"
            "  5.  Read the 💡 Recommendations tab for specific tuning suggestions.\n"
            "  6.  Run scenarios in the 🧪 Simulation tab to predict lap time changes.\n"
            "  7.  See 📖 Help for a full guide on reading every chart."
        )
        self.instructions.setStyleSheet(
            "background-color:#0d1b2a; border:1px solid #333366; "
            "border-radius:6px; padding:14px; color:#aaaacc; "
            "font-size:12px; line-height:1.7;"
        )
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)
        layout.addStretch()

    def _build_multi_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "Use this tab to load multiple CSV files from one AiM device "
            "(e.g. practice, qualifying, and race from the same event).  "
            "All sessions are added to the session list and you can compare any two."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#aaaacc; font-size:12px; padding:4px;")
        layout.addWidget(info)

        row = QHBoxLayout()
        self._multi_name_edit = QLineEdit()
        self._multi_name_edit.setPlaceholderText("Driver / team name (optional)")
        row.addWidget(QLabel("Name:"))
        row.addWidget(self._multi_name_edit, 1)

        browse_btn = QPushButton("📂  Browse — Select Multiple Files…")
        browse_btn.clicked.connect(self._browse_multiple)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self._multi_file_list = QListWidget()
        self._multi_file_list.setMaximumHeight(100)
        self._multi_file_list.setStyleSheet("font-size:11px; color:#aaaacc;")
        layout.addWidget(self._multi_file_list)

        load_row = QHBoxLayout()
        self._multi_load_btn = QPushButton("▶  Load All Listed Files")
        self._multi_load_btn.setEnabled(False)
        self._multi_load_btn.setStyleSheet(
            "QPushButton:enabled { background:#0f3460; font-weight:bold; }"
        )
        self._multi_load_btn.clicked.connect(self._emit_multi_load)
        load_row.addWidget(self._multi_load_btn)
        clear_btn = QPushButton("✖  Clear List")
        clear_btn.clicked.connect(self._clear_multi_list)
        load_row.addWidget(clear_btn)
        load_row.addStretch()
        layout.addLayout(load_row)

        self._multi_paths: List[str] = []
        return widget

    def _browse_multiple(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select AiM / SCCA CSV Files", "",
            "CSV files (*.csv);;All files (*)"
        )
        if paths:
            self._multi_paths = paths
            self._multi_file_list.clear()
            for p in paths:
                self._multi_file_list.addItem(p.split("/")[-1])
            self._multi_load_btn.setEnabled(True)

    def _clear_multi_list(self) -> None:
        self._multi_paths = []
        self._multi_file_list.clear()
        self._multi_load_btn.setEnabled(False)

    def _emit_multi_load(self) -> None:
        name = self._multi_name_edit.text().strip()
        self.load_multiple_requested.emit(self._multi_paths, name)

    # ------------------------------------------------------------------
    # Public update methods called from MainWindow
    # ------------------------------------------------------------------

    def update_session1_info(self, raw: "RawSessionData", analysis: "SessionAnalysis") -> None:
        self.driver1_panel.update_info(raw, analysis)

    def update_session2_info(self, raw: "RawSessionData", analysis: "SessionAnalysis") -> None:
        self.driver2_panel.update_info(raw, analysis)

    def update_session_list(self, manager: "SessionManager") -> None:
        self.session_list_panel.refresh(manager)
        self.session_list_panel.setVisible(len(manager) > 1)
