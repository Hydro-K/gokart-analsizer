"""
Main application window — EV Kart Data Analyzer.
Owns all session data and mediates tab communication.
"""

from __future__ import annotations
import os
from typing import Optional, List

from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QStatusBar,
    QAction, QMenuBar, QFileDialog, QMessageBox, QLabel,
    QHBoxLayout,
)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPalette, QColor

from src.data_loader import RawSessionData, load_aim_csv
from src.lap_analyzer import SessionAnalysis, analyse_session
from src.alltrax_settings import AlltraxSettings
from src.gear_ratio import GearRatioConfig
from src.setup_log import SetupLog
from src.recommendations import RecommendationEngine, Recommendation
from src.export_manager import export_all
from src.session_manager import SessionManager, LoadedSession
from src.competition_rules import get_rules, ComplianceChecker
from src.alltrax_importer import import_alltrax_file, export_alltrax_aep

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
from src.gui.simulation_tab import SimulationTab
from src.gui.deep_analysis_tab import DeepAnalysisTab
from src.gui.telemetry_tab import TelemetryTab
from src.gui.session_logger_tab import SessionLoggerTab
from src.gui.rules_tab import RulesTab
from src.gui.help_tab import HelpTab


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
QListWidget {
    background-color: #0d1b2a;
    border: 1px solid #333366;
    color: #e0e0e0;
}
QListWidget::item:selected {
    background-color: #0f3460;
    color: #ffffff;
}
"""


class MainWindow(QMainWindow):
    session1_loaded   = pyqtSignal(object)       # SessionAnalysis
    session2_loaded   = pyqtSignal(object, object)  # SessionAnalysis, SessionAnalysis
    settings_changed  = pyqtSignal(object, object)  # AlltraxSettings, GearRatioConfig
    recommendations_ready = pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("EV Kart Data Analyzer — Purdue Grand Prix")
        self.resize(1440, 900)
        self.setStyleSheet(DARK_STYLE)

        # Session state
        self.session_manager = SessionManager()
        self.session1: Optional[SessionAnalysis] = None
        self.session2: Optional[SessionAnalysis] = None
        self.settings  = AlltraxSettings()
        self.gear      = GearRatioConfig()
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

        # ---- File menu ---------------------------------------------------
        file_menu = mb.addMenu("&File")

        act_open1 = QAction("Load Session (Driver 1)…", self)
        act_open1.setShortcut("Ctrl+O")
        act_open1.triggered.connect(self._load_session1_dialog)
        file_menu.addAction(act_open1)

        act_open_multi = QAction("Load Multiple SCCA/AiM Files…", self)
        act_open_multi.setShortcut("Ctrl+Shift+O")
        act_open_multi.triggered.connect(self._load_multiple_dialog)
        file_menu.addAction(act_open_multi)

        file_menu.addSeparator()

        act_import_alltrax = QAction("Import Alltrax Settings (.aep)…", self)
        act_import_alltrax.setShortcut("Ctrl+I")
        act_import_alltrax.triggered.connect(self._import_alltrax_dialog)
        file_menu.addAction(act_import_alltrax)

        act_export_alltrax = QAction("Export Alltrax Settings (.aep)…", self)
        act_export_alltrax.triggered.connect(self._export_alltrax_dialog)
        file_menu.addAction(act_export_alltrax)

        act_save_settings = QAction("Save Settings (JSON)…", self)
        act_save_settings.triggered.connect(self._save_settings_dialog)
        file_menu.addAction(act_save_settings)

        act_load_settings = QAction("Load Settings (JSON)…", self)
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

        # ---- Tools menu --------------------------------------------------
        tools_menu = mb.addMenu("&Tools")

        act_gen_sample = QAction("Generate Sample Data…", self)
        act_gen_sample.triggered.connect(self._generate_sample)
        tools_menu.addAction(act_gen_sample)

        act_compliance = QAction("Run Compliance Check", self)
        act_compliance.setShortcut("Ctrl+R")
        act_compliance.triggered.connect(self._run_compliance_check)
        tools_menu.addAction(act_compliance)

        tools_menu.addSeparator()

        act_help_tab = QAction("Open Help / User Guide", self)
        act_help_tab.setShortcut("F1")
        act_help_tab.triggered.connect(self._go_to_help)
        tools_menu.addAction(act_help_tab)

    def _build_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        # Instantiate all tabs
        self.session_tab        = SessionTab(self)
        self.lap_times_tab      = LapTimesTab(self)
        self.speed_trace_tab    = SpeedTraceTab(self)
        self.corner_tab         = CornerTab(self)
        self.accel_tab          = AccelTab(self)
        self.throttle_zone_tab  = ThrottleZoneTab(self)
        self.comparison_tab     = ComparisonTab(self)
        self.deep_analysis_tab  = DeepAnalysisTab(self)
        self.telemetry_tab      = TelemetryTab(self)
        self.simulation_tab     = SimulationTab(self)
        self.settings_tab       = SettingsTab(self)
        self.recommendations_tab = RecommendationsTab(self)
        self.rules_tab          = RulesTab(self)
        self.setup_log_tab      = SetupLogTab(self)
        self.session_logger_tab = SessionLoggerTab(self)
        self.export_tab         = ExportTab(self)
        self.help_tab           = HelpTab(self)

        # Add tabs in logical order
        self.tabs.addTab(self.session_tab,          "📂  Session")
        self.tabs.addTab(self.lap_times_tab,        "⏱  Lap Times")
        self.tabs.addTab(self.speed_trace_tab,      "📈  Speed Trace")
        self.tabs.addTab(self.corner_tab,           "🔵  Corners")
        self.tabs.addTab(self.accel_tab,            "⚡  Acceleration")
        self.tabs.addTab(self.throttle_zone_tab,    "🎚  Throttle Zones")
        self.tabs.addTab(self.comparison_tab,       "👥  Comparison")
        self.tabs.addTab(self.deep_analysis_tab,    "🔬  Deep Analysis")
        self.tabs.addTab(self.telemetry_tab,        "🗺  Telemetry")
        self.tabs.addTab(self.simulation_tab,       "🧪  Simulation")
        self.tabs.addTab(self.settings_tab,         "⚙️  Settings")
        self.tabs.addTab(self.recommendations_tab,  "💡  Recommendations")
        self.tabs.addTab(self.rules_tab,            "🏁  Rules")
        self.tabs.addTab(self.setup_log_tab,        "📋  Setup Log")
        self.tabs.addTab(self.session_logger_tab,   "🌡  Session Logger")
        self.tabs.addTab(self.export_tab,           "📤  Export")
        self.tabs.addTab(self.help_tab,             "📖  Help")

    def _build_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._status_label = QLabel("No session loaded — use File → Load Session or the Session tab")
        self.status_bar.addWidget(self._status_label, 1)

        self._compliance_label = QLabel("")
        self._compliance_label.setStyleSheet("color:#FFD700; padding:0 8px;")
        self.status_bar.addPermanentWidget(self._compliance_label)

    def _connect_signals(self) -> None:
        # Session loading
        self.session_tab.load_session1_requested.connect(self._load_session1)
        self.session_tab.load_session2_requested.connect(self._load_session2)
        self.session_tab.load_multiple_requested.connect(self._load_multiple)

        # Settings changes → all consumers
        self.settings_tab.settings_changed.connect(self._on_settings_changed)

        # session1 → single-session analysis tabs
        self.session1_loaded.connect(self.lap_times_tab.set_session)
        self.session1_loaded.connect(self.speed_trace_tab.set_session)
        self.session1_loaded.connect(self.corner_tab.set_session)
        self.session1_loaded.connect(self.accel_tab.set_session)
        self.session1_loaded.connect(self.throttle_zone_tab.set_session)
        self.session1_loaded.connect(self.deep_analysis_tab.set_session)
        self.session1_loaded.connect(self.telemetry_tab.set_session)
        self.session1_loaded.connect(self.simulation_tab.set_session)
        self.session1_loaded.connect(self.export_tab.on_session_loaded)

        # session2 (comparison)
        self.session2_loaded.connect(self.comparison_tab.set_sessions)

        # Settings → analysis tabs
        self.settings_changed.connect(self.speed_trace_tab.on_settings_changed)
        self.settings_changed.connect(self.accel_tab.on_settings_changed)
        self.settings_changed.connect(self.simulation_tab.set_base_settings)
        self.settings_changed.connect(self.rules_tab.on_settings_changed)

        # Recommendations
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

    def _load_multiple_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open Multiple AiM / SCCA CSV Files", "",
            "CSV files (*.csv);;All files (*)"
        )
        if paths:
            self._load_multiple(paths, "")

    def _load_session1(self, filepath: str, driver_name: str) -> None:
        try:
            raw = load_aim_csv(filepath)
            raw.driver_name = driver_name or raw.driver_name
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

            # Show any data quality warnings
            if raw.warnings:
                self.status_bar.showMessage(
                    "⚠ Data warnings: " + "  •  ".join(raw.warnings), 8000
                )

        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to load session:\n{exc}")

    def _load_session2(self, filepath: str, driver_name: str) -> None:
        try:
            raw = load_aim_csv(filepath)
            raw.driver_name = driver_name or raw.driver_name
            analysis = analyse_session(
                raw.time, raw.speed, raw.lat, raw.lon,
                raw.beacon, raw.has_beacon,
            )
            analysis.raw = raw  # type: ignore[attr-defined]
            self.session2 = analysis
            self.session_tab.update_session2_info(raw, analysis)
            if self.session1:
                self.session2_loaded.emit(self.session1, self.session2)
                self.comparison_tab.set_sessions(self.session1, self.session2)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to load comparison:\n{exc}")

    def _load_multiple(self, filepaths: List[str], driver_name: str) -> None:
        """Load several CSV files — adds them to the session manager and updates comparison tab."""
        if not filepaths:
            return
        loaded = []
        errors = []
        for fp in filepaths:
            try:
                s = self.session_manager.load_file(fp, driver_name)
                loaded.append(s)
            except Exception as exc:
                errors.append(f"{os.path.basename(fp)}: {exc}")

        if errors:
            QMessageBox.warning(
                self, "Load Warnings",
                f"Loaded {len(loaded)} files with {len(errors)} error(s):\n"
                + "\n".join(errors)
            )

        if loaded:
            # Use the first file as session1
            first = loaded[0]
            self.session1 = first.analysis
            self.session1_loaded.emit(first.analysis)
            self.session_tab.update_session1_info(first.raw, first.analysis)
            self._run_recommendations()

            # If more than one, load the second as session2
            if len(loaded) >= 2:
                second = loaded[1]
                self.session2 = second.analysis
                self.session_tab.update_session2_info(second.raw, second.analysis)
                self.session2_loaded.emit(self.session1, self.session2)

            # Update session list in session tab
            self.session_tab.update_session_list(self.session_manager)

            self._status_label.setText(
                f"Loaded {len(loaded)} session(s)  |  "
                f"Best overall: {self.session_manager.best_session.analysis.best_lap.lap_time_str}"
            )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _on_settings_changed(self, settings: AlltraxSettings, gear: GearRatioConfig) -> None:
        self.settings = settings
        self.gear     = gear
        self.settings_changed.emit(settings, gear)
        if self.session1:
            self._run_recommendations()
        self._quick_compliance_check(settings, gear)

    def _quick_compliance_check(self, settings: AlltraxSettings, gear: GearRatioConfig) -> None:
        """Flash status bar warning if settings violate rules."""
        rules = get_rules()
        checker = ComplianceChecker(rules)
        report = checker.check(settings, gear)
        if report.fail_count:
            self._compliance_label.setStyleSheet("color:#ff4444; font-weight:bold; padding:0 8px;")
            self._compliance_label.setText(
                f"⛔ {report.fail_count} RULE VIOLATION(S) — open Rules tab"
            )
        elif report.warn_count:
            self._compliance_label.setStyleSheet("color:#FFD700; padding:0 8px;")
            self._compliance_label.setText(f"⚠ {report.warn_count} warning(s)")
        else:
            self._compliance_label.setStyleSheet("color:#00cc66; padding:0 8px;")
            self._compliance_label.setText("✅ Compliant")

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

    def _import_alltrax_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Alltrax Settings",
            "",
            "Alltrax files (*.aep *.txt *.csv *.json);;All files (*)"
        )
        if not path:
            return
        try:
            settings, warnings = import_alltrax_file(path)
            self.settings_tab.load_settings(settings)
            msg = f"Successfully imported settings from:\n{path}"
            if warnings:
                msg += "\n\nNotes:\n" + "\n".join(f"• {w}" for w in warnings)
            QMessageBox.information(self, "Import Complete", msg)
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", f"Could not import file:\n{exc}")

    def _export_alltrax_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Alltrax Settings",
            "controller_settings.aep",
            "Alltrax AEP (*.aep);;JSON (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            if path.lower().endswith(".json"):
                self.settings.to_json(path)
            else:
                export_alltrax_aep(self.settings, path)
            QMessageBox.information(
                self, "Export Complete",
                f"Settings exported to:\n{path}\n\n"
                "Load in Alltrax Toolkit via File → Load Settings, "
                "then click 'Program Controller' to write to hardware."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

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
    # Compliance (menu shortcut)
    # ------------------------------------------------------------------

    def _run_compliance_check(self) -> None:
        # Switch to rules tab and run check
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).endswith("Rules"):
                self.tabs.setCurrentIndex(i)
                break
        self.rules_tab._run_check()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_all_dialog(self) -> None:
        output_dir = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if not output_dir:
            return
        figures = {}
        for tab_name, tab in [
            ("speed_trace",  self.speed_trace_tab),
            ("corners",      self.corner_tab),
            ("acceleration", self.accel_tab),
            ("throttle",     self.throttle_zone_tab),
            ("comparison",   self.comparison_tab),
            ("simulation",   self.simulation_tab),
        ]:
            fig = getattr(tab, "figure", None)
            if fig is not None:
                figures[tab_name] = fig

        session_name = "session"
        if self.session1:
            raw = getattr(self.session1, "raw", None)
            session_name = raw.filename.replace(".csv", "") if raw else "session"

        written = export_all(
            output_dir, figures, self.recommendations,
            self.setup_log, self.settings, self.gear, session_name,
        )
        QMessageBox.information(
            self, "Export Complete",
            f"Exported {len(written)} files to:\n{output_dir}"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _go_to_help(self) -> None:
        for i in range(self.tabs.count()):
            if "Help" in self.tabs.tabText(i):
                self.tabs.setCurrentIndex(i)
                break

    def _generate_sample(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Sample CSV", "sample_lap.csv", "CSV files (*.csv)"
        )
        if path:
            try:
                import sample_data_generator as sdg
                sdg.generate(path)
                QMessageBox.information(self, "Done", f"Sample data written to:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
