"""Export tab: select what to export and pick output directory."""

from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QLabel, QFileDialog, QLineEdit, QTextEdit,
)
from PyQt5.QtCore import Qt


class ExportTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_loaded = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Export Session Data")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e94560;")
        layout.addWidget(title)

        # What to export
        what_group = QGroupBox("Export Contents")
        what_layout = QVBoxLayout(what_group)
        self._charts_cb = QCheckBox("Charts (PNG — speed trace, corners, acceleration, comparison)")
        self._charts_cb.setChecked(True)
        self._recs_cb = QCheckBox("Recommendations (text file)")
        self._recs_cb.setChecked(True)
        self._log_cb = QCheckBox("Setup Log (text file)")
        self._log_cb.setChecked(True)
        self._settings_cb = QCheckBox("Alltrax Settings (JSON — reload next session)")
        self._settings_cb.setChecked(True)
        self._gear_cb = QCheckBox("Gear Ratio Config (JSON)")
        self._gear_cb.setChecked(True)
        for cb in (self._charts_cb, self._recs_cb, self._log_cb,
                   self._settings_cb, self._gear_cb):
            what_layout.addWidget(cb)
        layout.addWidget(what_group)

        # Output directory
        dir_group = QGroupBox("Output Directory")
        dir_layout = QHBoxLayout(dir_group)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Select output folder…")
        dir_layout.addWidget(self._dir_edit, 1)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        dir_layout.addWidget(browse_btn)
        layout.addWidget(dir_group)

        # Export button
        self._export_btn = QPushButton("Export Selected")
        self._export_btn.setStyleSheet(
            "background-color: #e94560; font-weight: bold; font-size: 14px; padding: 10px;"
        )
        self._export_btn.clicked.connect(self._export)
        layout.addWidget(self._export_btn)

        # Result log
        self._result_edit = QTextEdit()
        self._result_edit.setReadOnly(True)
        self._result_edit.setPlaceholderText("Export results will appear here…")
        self._result_edit.setMaximumHeight(200)
        layout.addWidget(self._result_edit)

        layout.addStretch()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if d:
            self._dir_edit.setText(d)

    def on_session_loaded(self, _):
        self._session_loaded = True

    def _export(self):
        import os
        from datetime import datetime
        from src import export_manager

        mw = self.parent()
        output_dir = self._dir_edit.text().strip()
        if not output_dir:
            self._result_edit.setPlainText("Please select an output directory first.")
            return

        figures = {}
        if self._charts_cb.isChecked() and hasattr(mw, "speed_trace_tab"):
            for name, tab in [
                ("speed_trace", mw.speed_trace_tab),
                ("corners", mw.corner_tab),
                ("acceleration", mw.accel_tab),
                ("throttle_zones", mw.throttle_zone_tab),
                ("comparison", mw.comparison_tab),
            ]:
                fig = getattr(tab, "figure", None)
                if fig is not None:
                    figures[name] = fig

        recs = getattr(mw, "recommendations", []) if self._recs_cb.isChecked() else []
        log = getattr(mw, "setup_log", None)
        from src.setup_log import SetupLog
        if not self._log_cb.isChecked():
            log = SetupLog()
        settings = getattr(mw, "settings", None)
        from src.alltrax_settings import AlltraxSettings
        if not self._settings_cb.isChecked():
            settings = AlltraxSettings()
        gear = getattr(mw, "gear", None)
        from src.gear_ratio import GearRatioConfig
        if not self._gear_cb.isChecked():
            gear = GearRatioConfig()

        session_name = "session"
        if hasattr(mw, "session1") and mw.session1:
            raw = getattr(mw.session1, "raw", None)
            if raw:
                session_name = raw.filename.replace(".csv", "")

        try:
            written = export_manager.export_all(
                output_dir, figures, recs, log, settings, gear, session_name
            )
            lines = [f"Exported {len(written)} file(s) to {output_dir}:", ""]
            for path in written:
                lines.append(f"  {os.path.basename(path)}")
            self._result_edit.setPlainText("\n".join(lines))
        except Exception as exc:
            self._result_edit.setPlainText(f"Export failed:\n{exc}")
