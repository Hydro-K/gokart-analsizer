"""
Main application window.  Owns all session data and mediates tab communication.
"""

from __future__ import annotations
import os
from typing import Optional, List

from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QStatusBar,
    QAction, QMenuBar, QFileDialog, QMessageBox, QLabel,
    QHBoxLayout,
)
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtGui import QPalette, QColor

from src.data_loader import RawSessionData, load_aim_csv
from src.lap_analyzer import SessionAnalysis, analyse_session
from src.alltrax_settings import AlltraxSettings
from src.gear_ratio import GearRatioConfig
from src.setup_log import SetupLog
from src.recommendations import RecommendationEngine, Recommendation
from src.export_manager import export_all

from src.gui.session_tab import SessionTab
from src.gui.lap_times_tab import LapTimesTab
from src.gui.speed_trace_tab import SpeedTraceTab
from src.gui.corner_tab import CornerTab
from src.gui.accel_tab import AccelTab
from src.gui.throttle_zone_tab import ThrottleZoneTab
from src.gui.comparison_tab import ComparisonTab
from src.gui.settings_tab import SettingsTab
from src.gui.recommendations_tab import RecommendationsTab
from src.gui.setup_log_tab import SetupLogTab
from src.gui.export_tab import ExportTab


DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QTabWidget::pane {
    border: 1px solid #333355;
    background-color: #16213e;
}
QTabBar::tab {
    background-color: #0f3460;
    color: #aaaacc;
    padding: 6px 14px;
    border: 1px solid #333355;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    min-width: 80px;
}
QTabBar::tab:selected {
    background-color: #e94560;
    color: #ffffff;
}
QTabBar::tab:hover:!selected {
    background-color: #1a4080;
}
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: 1px solid #333366;
    border-radius: 4px;
    padding: 5px 12px;
}
QPushButton:hover {
    background-color: #1a4080;
}
QPushButton:pressed {
    background-color: #e94560;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0d1b2a;
    color: #e0e0e0;
    border: 1px solid #333366;
    border-radius: 3px;
    padding: 3px;
}
QGroupBox {
    border: 1px solid #333366;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    color: #aaaaee;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
}
QTableWidget {
    background-color: #0d1b2a;
    gridline-color: #222244;
    color: #e0e0e0;
    border: 1px solid #333366;
}
QHeaderView::section {
    background-color: #0f3460;
    color: #aaaaee;
    border: 1px solid #222244;
    padding: 4px;
}
QSlider::groove:horizontal {
    height: 6px;
    background-color: #222244;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background-color: #e94560;
    border-radius: 7px;
    width: 14px;
    height: 14px;
    margin: -4px 0;
}
QSlider::sub-page:horizontal {
    background-color: #1a4080;
    border-radius: 3px;
}
QScrollBar:vertical {
    background-color: #0d1b2a;
    width: 12px;
}
QScrollBar::handle:vertical {
    background-color: #333366;
    border-radius: 4px;
}
QTextEdit, QPlainTextEdit {
    background-color: #0d1b2a;
    color: #e0e0e0;
    border: 1px solid #333366;
}
QCheckBox {
    color: #e0e0e0;
}
QLabel {
    color: #e0e0e0;
}
QStatusBar {
    background-color: #0f3460;
    color: #aaaacc;
}
"""


class MainWindow(QMainWindow):
    # Emitted when either session's data is updated
    session1_loaded = pyqtSignal(object)      # SessionAnalysis
    session2_loaded = pyqtSignal(object)      # SessionAnalysis | None
    settings_changed = pyqtSignal(object, object)  # AlltraxSettings, GearRatioConfig
    recommendations_ready = pyqtSignal(list)  # List[Recommendation]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("EV Kart Data Analyzer — Purdue Grand Prix")
        self.resize(1400, 900)
        self.setStyleSheet(DARK_STYLE)

        self.session1: Optional[SessionAnalysis] = None
        self.session2: Optional[SessionAnalysis] = None
        self.settings = AlltraxSettings()
        self.gear = GearRatioConfig()
        self.setup_log = SetupLog()
        self.recommendations: List[Recommendation] = []

        self._build_menu()
        self._build_tabs()
        self._build_status_bar()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        act_open1 = QAction("Load Session (Driver 1)…", self)
        act_open1.setShortcut("Ctrl+O")
        act_open1.triggered.connect(self._load_session1_dialog)
        file_menu.addAction(act_open1)

        act_open2 = QAction("Load Comparison (Driver 2)…", self)
        act_open2.setShortcut("Ctrl+Shift+O")
        act_open2.triggered.connect(self._load_session2_dialog)
        file_menu.addAction(act_open2)

        file_menu.addSeparator()

        act_save_settings = QAction("Save Alltrax Settings…", self)
        act_save_settings.triggered.connect(self._save_settings_dialog)
        file_menu.addAction(act_save_settings)

        act_load_settings = QAction("Load Alltrax Settings…", self)
        act_load_settings.triggered.connect(self._load_settings_dialog)
        file_menu.addAction(act_load_settings)

        file_menu.addSeparator()

        act_export = QAction("Export All…", self)
        act_export.setShortcut("Ctrl+E")
        act_export.triggered.connect(self._export_all_dialog)
        file_menu.addAction(act_export)

        file_menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        tools_menu = mb.addMenu("&Tools")
        act_gen_sample = QAction("Generate Sample Data…", self)
        act_gen_sample.triggered.connect(self._generate_sample)
        tools_menu.addAction(act_gen_sample)

    def _build_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        self.session_tab = SessionTab(self)
        self.lap_times_tab = LapTimesTab(self)
        self.speed_trace_tab = SpeedTraceTab(self)
        self.corner_tab = CornerTab(self)
        self.accel_tab = AccelTab(self)
        self.throttle_zone_tab = ThrottleZoneTab(self)
        self.comparison_tab = ComparisonTab(self)
        self.settings_tab = SettingsTab(self)
        self.recommendations_tab = RecommendationsTab(self)
        self.setup_log_tab = SetupLogTab(self)
        self.export_tab = ExportTab(self)

        self.tabs.addTab(self.session_tab, "Session")
        self.tabs.addTab(self.lap_times_tab, "Lap Times")
        self.tabs.addTab(self.speed_trace_tab, "Speed Trace")
        self.tabs.addTab(self.corner_tab, "Corners")
        self.tabs.addTab(self.accel_tab, "Acceleration")
        self.tabs.addTab(self.throttle_zone_tab, "Throttle Zones")
        self.tabs.addTab(self.comparison_tab, "Comparison")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.recommendations_tab, "Recommendations")
        self.tabs.addTab(self.setup_log_tab, "Setup Log")
        self.tabs.addTab(self.export_tab, "Export")

    def _build_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._status_label = QLabel("No session loaded")
        self.status_bar.addWidget(self._status_label)

    def _connect_signals(self) -> None:
        self.session_tab.load_session1_requested.connect(self._load_session1)
        self.session_tab.load_session2_requested.connect(self._load_session2)

        self.settings_tab.settings_changed.connect(self._on_settings_changed)

        self.session1_loaded.connect(self.lap_times_tab.set_session)
        self.session1_loaded.connect(self.speed_trace_tab.set_session)
        self.session1_loaded.connect(self.corner_tab.set_session)
        self.session1_loaded.connect(self.accel_tab.set_session)
        self.session1_loaded.connect(self.throttle_zone_tab.set_session)
        self.session1_loaded.connect(self.export_tab.on_session_loaded)

        self.session2_loaded.connect(self.comparison_tab.set_sessions)

        self.settings_changed.connect(self.speed_trace_tab.on_settings_changed)
        self.settings_changed.connect(self.accel_tab.on_settings_changed)

        self.recommendations_ready.connect(self.recommendations_tab.set_recommendations)
        self.recommendations_tab.apply_all_clicked.connect(self._apply_recommendations)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_session1_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Session CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if path:
            self._load_session1(path, "Driver 1")

    def _load_session2_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Comparison CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if path:
            self._load_session2(path, "Driver 2")

    def _load_session1(self, filepath: str, driver_name: str) -> None:
        try:
            raw = load_aim_csv(filepath)
            raw.driver_name = driver_name
            analysis = analyse_session(
                raw.time, raw.speed, raw.lat, raw.lon,
                raw.beacon, raw.has_beacon,
            )
            analysis.raw = raw  # type: ignore[attr-defined]
            self.session1 = analysis
            self._status_label.setText(
                f"Driver 1: {driver_name}  |  {raw.filename}  |  "
                f"{len(analysis.laps)} laps  |  Best: {analysis.best_lap.lap_time_str}"
            )
            self.session1_loaded.emit(analysis)
            self._run_recommendations()
            self.session_tab.update_session1_info(raw, analysis)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to load session:\n{exc}")

    def _load_session2(self, filepath: str, driver_name: str) -> None:
        try:
            raw = load_aim_csv(filepath)
            raw.driver_name = driver_name
            analysis = analyse_session(
                raw.time, raw.speed, raw.lat, raw.lon,
                raw.beacon, raw.has_beacon,
            )
            analysis.raw = raw  # type: ignore[attr-defined]
            self.session2 = analysis
            self.session2_loaded.emit(analysis)
            self.session_tab.update_session2_info(raw, analysis)
            if self.session1:
                self.comparison_tab.set_sessions(self.session1, self.session2)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to load comparison:\n{exc}")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _on_settings_changed(self, settings: AlltraxSettings, gear: GearRatioConfig) -> None:
        self.settings = settings
        self.gear = gear
        self.settings_changed.emit(settings, gear)
        if self.session1:
            self._run_recommendations()

    def _save_settings_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Settings", "alltrax_settings.json", "JSON (*.json)"
        )
        if path:
            self.settings.to_json(path)

    def _load_settings_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Settings", "", "JSON (*.json)"
        )
        if path:
            try:
                s = AlltraxSettings.from_json(path)
                self.settings_tab.load_settings(s)
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Could not load settings:\n{exc}")

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def _run_recommendations(self) -> None:
        if self.session1 is None:
            return
        try:
            engine = RecommendationEngine(self.session1, self.settings, self.gear)
            self.recommendations = engine.generate()
            self.recommendations_ready.emit(self.recommendations)
        except Exception:
            pass

    def _apply_recommendations(self, recs: list) -> None:
        self.settings_tab.apply_recommendations(recs, self.setup_log)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_all_dialog(self) -> None:
        output_dir = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if not output_dir:
            return
        figures = {}
        for tab_name, tab in [
            ("speed_trace", self.speed_trace_tab),
            ("corners", self.corner_tab),
            ("acceleration", self.accel_tab),
            ("throttle_zones", self.throttle_zone_tab),
            ("comparison", self.comparison_tab),
        ]:
            fig = getattr(tab, "figure", None)
            if fig is not None:
                figures[tab_name] = fig

        session_name = "session"
        if self.session1:
            session_name = getattr(self.session1, "raw", None)
            session_name = session_name.filename.replace(".csv", "") if session_name else "session"

        written = export_all(
            output_dir, figures, self.recommendations,
            self.setup_log, self.settings, self.gear, session_name,
        )
        QMessageBox.information(
            self, "Export Complete",
            f"Exported {len(written)} files to:\n{output_dir}"
        )

    # ------------------------------------------------------------------
    # Sample data
    # ------------------------------------------------------------------

    def _generate_sample(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Sample CSV", "sample_lap.csv", "CSV files (*.csv)"
        )
        if path:
            try:
                import sample_data_generator as sdg
                sdg.generate(path)
                QMessageBox.information(
                    self, "Done", f"Sample data written to:\n{path}"
                )
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
