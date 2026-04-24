"""
Session Telemetry Logger Tab.

Post-session data entry: tyre temps & PSI (4 corners), motor temp,
battery temp & voltage, brake temps, ambient conditions, session results.
Persists to ~/.evkart_sessions.json across runs.

Three sub-tabs:
  • New Reading  – entry form with colour-coded status indicators
  • History      – scrollable table of all saved readings
  • Trends       – multi-chart view of key metrics over sessions
"""

from __future__ import annotations
from typing import Optional, List
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QDoubleSpinBox, QSpinBox, QComboBox,
    QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QScrollArea, QFrame, QSizePolicy, QLineEdit, QFileDialog,
    QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from src.session_logger import (
    SessionDatabase, TelemetryReading, STATUS_COLORS, THRESHOLDS,
    SESSION_TYPES, TRACK_CONDITIONS, temp_status,
)

CHART_BG = "#0d1b2a"
GRID_C   = "#1a2a3a"


# ---------------------------------------------------------------------------
# Coloured sensor spinbox
# ---------------------------------------------------------------------------

class _SensorSpin(QWidget):
    """
    A QDoubleSpinBox with a coloured status dot that updates as the value
    changes against the threshold table.
    """
    def __init__(self, threshold_key: str, mn: float, mx: float,
                 default: float, step: float = 1.0,
                 suffix: str = "", decimals: int = 1, parent=None):
        super().__init__(parent)
        self._key = threshold_key
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.spin = QDoubleSpinBox()
        self.spin.setRange(mn, mx)
        self.spin.setSingleStep(step)
        self.spin.setValue(default)
        self.spin.setDecimals(decimals)
        self.spin.setSuffix(suffix)
        self.spin.setSpecialValueText("—")
        self.spin.setMinimum(mn - step)   # one step below min = "not set"
        self.spin.setValue(mn - step)     # start "not set"
        layout.addWidget(self.spin)

        self._dot = QLabel("●")
        self._dot.setStyleSheet("color: #555577; font-size: 14px;")
        self._dot.setFixedWidth(18)
        layout.addWidget(self._dot)

        self.spin.valueChanged.connect(self._update_dot)

    def _update_dot(self, v):
        mn_real = self.spin.minimum()
        if v <= mn_real + 1e-9:
            self._dot.setStyleSheet("color: #555577; font-size: 14px;")
            return
        status = temp_status(v, self._key)
        color = STATUS_COLORS.get(status, "#555577")
        self._dot.setStyleSheet(f"color: {color}; font-size: 14px;")

    def value(self) -> Optional[float]:
        v = self.spin.value()
        if v <= self.spin.minimum() + 1e-9:
            return None
        return v

    def set_value(self, v: Optional[float]) -> None:
        self.spin.setValue(v if v is not None else self.spin.minimum())


# ---------------------------------------------------------------------------
# 4-corner tyre grid widget
# ---------------------------------------------------------------------------

class _TyreGrid(QGroupBox):
    """Displays FL/FR/RL/RR fields for temps and PSI in a kart-footprint layout."""

    def __init__(self, title: str = "Tyre Data", parent=None):
        super().__init__(title, parent)
        outer = QVBoxLayout(self)

        # Column labels
        hdr = QHBoxLayout()
        for t in ("", "Left", "Right"):
            lbl = QLabel(t)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #8888aa; font-size: 10px;")
            hdr.addWidget(lbl, 1)
        outer.addLayout(hdr)

        grid = QGridLayout()
        grid.setSpacing(6)

        self._temp_spins: dict[str, _SensorSpin] = {}
        self._psi_spins:  dict[str, _SensorSpin] = {}

        for row, (axle, corners) in enumerate([("Front", ("fl","fr")),
                                               ("Rear",  ("rl","rr"))]):
            axle_lbl = QLabel(axle)
            axle_lbl.setAlignment(Qt.AlignCenter)
            axle_lbl.setStyleSheet("color: #aaaacc; font-weight: bold;")
            grid.addWidget(axle_lbl, row * 2, 0)

            for col, corner in enumerate(corners):
                cell = QGroupBox(corner.upper())
                cell.setStyleSheet(
                    "QGroupBox { border: 1px solid #333366; border-radius: 4px; "
                    "margin-top: 6px; padding-top: 4px; color: #8888aa; font-size: 10px; }"
                )
                cl = QVBoxLayout(cell)
                cl.setSpacing(2)

                temp_lbl = QLabel("Temp (°C)")
                temp_lbl.setStyleSheet("color: #888888; font-size: 9px;")
                temp = _SensorSpin("tyre_temp", 0, 200, 70, suffix=" °C")
                cl.addWidget(temp_lbl)
                cl.addWidget(temp)

                psi_lbl = QLabel("PSI (cold)")
                psi_lbl.setStyleSheet("color: #888888; font-size: 9px;")
                psi = _SensorSpin("tyre_psi", 8, 25, 16, step=0.5, suffix=" PSI")
                cl.addWidget(psi_lbl)
                cl.addWidget(psi)

                grid.addWidget(cell, row * 2, col + 1)
                self._temp_spins[corner] = temp
                self._psi_spins[corner]  = psi

        outer.addLayout(grid)

    def get_temps(self) -> dict[str, Optional[float]]:
        return {c: s.value() for c, s in self._temp_spins.items()}

    def get_psi(self) -> dict[str, Optional[float]]:
        return {c: s.value() for c, s in self._psi_spins.items()}

    def set_temps(self, d: dict):
        for c, v in d.items():
            if c in self._temp_spins:
                self._temp_spins[c].set_value(v)

    def set_psi(self, d: dict):
        for c, v in d.items():
            if c in self._psi_spins:
                self._psi_spins[c].set_value(v)


# ---------------------------------------------------------------------------
# New Reading form
# ---------------------------------------------------------------------------

class _NewReadingWidget(QScrollArea):
    def __init__(self, db: SessionDatabase, history_tab, parent=None):
        super().__init__(parent)
        self._db = db
        self._history_tab = history_tab
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(10)
        self.setWidget(root)

        # ---- Session info row ------------------------------------------
        info_g = QGroupBox("Session Information")
        info_l = QGridLayout(info_g)

        info_l.addWidget(QLabel("Session type:"), 0, 0)
        self._session_type = QComboBox()
        self._session_type.addItems(SESSION_TYPES)
        info_l.addWidget(self._session_type, 0, 1)

        info_l.addWidget(QLabel("Track:"), 0, 2)
        self._track = QLineEdit()
        self._track.setPlaceholderText("e.g. Purdue Grand Prix Course")
        info_l.addWidget(self._track, 0, 3)

        info_l.addWidget(QLabel("Condition:"), 1, 0)
        self._condition = QComboBox()
        self._condition.addItems(TRACK_CONDITIONS)
        info_l.addWidget(self._condition, 1, 1)

        info_l.addWidget(QLabel("Ambient temp:"), 1, 2)
        self._ambient = _SensorSpin("tyre_temp", -20, 50, 22, suffix=" °C")
        info_l.addWidget(self._ambient, 1, 3)

        info_l.addWidget(QLabel("Best lap (s):"), 2, 0)
        self._best_lap = QDoubleSpinBox()
        self._best_lap.setRange(0, 600)
        self._best_lap.setSingleStep(0.001)
        self._best_lap.setDecimals(3)
        self._best_lap.setSpecialValueText("—")
        info_l.addWidget(self._best_lap, 2, 1)

        info_l.addWidget(QLabel("# Laps:"), 2, 2)
        self._num_laps = QSpinBox()
        self._num_laps.setRange(0, 200)
        self._num_laps.setSpecialValueText("—")
        info_l.addWidget(self._num_laps, 2, 3)

        info_l.addWidget(QLabel("Linked CSV file:"), 3, 0)
        self._data_file_lbl = QLabel("(none)")
        self._data_file_lbl.setStyleSheet("color: #8888aa;")
        info_l.addWidget(self._data_file_lbl, 3, 1, 1, 2)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_csv)
        info_l.addWidget(browse_btn, 3, 3)

        layout.addWidget(info_g)

        # ---- Tyre grid -------------------------------------------------
        self._tyre_grid = _TyreGrid("Tyre Temperatures & Pressures")
        layout.addWidget(self._tyre_grid)

        # ---- Brake temps -----------------------------------------------
        brake_g = QGroupBox("Brake Temperatures (°C)")
        brake_l = QGridLayout(brake_g)
        self._brake: dict[str, _SensorSpin] = {}
        for col, (corner, lbl) in enumerate([("fl","Front Left"),("fr","Front Right"),
                                              ("rl","Rear Left"), ("rr","Rear Right")]):
            brake_l.addWidget(QLabel(lbl+":"), 0, col)
            sp = _SensorSpin("brake_temp", 0, 800, 200, suffix=" °C")
            brake_l.addWidget(sp, 1, col)
            self._brake[corner] = sp
        layout.addWidget(brake_g)

        # ---- Drivetrain + battery --------------------------------------
        dt_g = QGroupBox("Drivetrain & Battery")
        dt_l = QGridLayout(dt_g)

        labels_spins = [
            ("Motor temp (°C):",       "motor_temp",       10, 150, 40,  " °C",  "motor_temp"),
            ("Controller temp (°C):",   "controller_temp",  10, 120, 35,  " °C",  "controller_temp"),
            ("Battery temp (°C):",      "battery_temp",     0,  80,  25,  " °C",  "battery_temp"),
            ("Battery voltage (V):",    "battery_voltage",  30, 65,  50.4," V",   "battery_voltage"),
            ("Battery SoC (%):",        "battery_soc",      0,  100, 100, " %",   "tyre_psi"),  # reuse ok key
        ]
        self._dt: dict[str, _SensorSpin] = {}
        for row, (lbl, key, mn, mx, default, sfx, thresh) in enumerate(labels_spins):
            dt_l.addWidget(QLabel(lbl), row, 0)
            sp = _SensorSpin(thresh, mn, mx, default, suffix=sfx)
            dt_l.addWidget(sp, row, 1)
            self._dt[key] = sp
        layout.addWidget(dt_g)

        # ---- Notes -----------------------------------------------------
        notes_g = QGroupBox("Session Notes")
        notes_l = QVBoxLayout(notes_g)
        self._notes = QTextEdit()
        self._notes.setPlaceholderText(
            "Driver feedback, setup changes made, issues observed, tyre compound used…"
        )
        self._notes.setMaximumHeight(120)
        notes_l.addWidget(self._notes)
        layout.addWidget(notes_g)

        # ---- Save button -----------------------------------------------
        save_btn = QPushButton("Save Reading")
        save_btn.setStyleSheet(
            "background-color: #e94560; font-weight: bold; font-size: 14px; padding: 10px;"
        )
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)
        layout.addStretch()

        self._data_file = ""

    def _browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Link AiM CSV File", "", "CSV files (*.csv);;All files (*)"
        )
        if path:
            self._data_file = path
            self._data_file_lbl.setText(path.split("/")[-1])

    def _save(self):
        ttemps = self._tyre_grid.get_temps()
        tpsi   = self._tyre_grid.get_psi()
        best   = self._best_lap.value() if self._best_lap.value() > 0 else None
        nlaps  = self._num_laps.value() if self._num_laps.value() > 0 else None

        r = TelemetryReading(
            session_type     = self._session_type.currentText(),
            track            = self._track.text().strip(),
            track_condition  = self._condition.currentText(),
            ambient_temp_c   = self._ambient.value(),
            best_lap_time_s  = best,
            num_laps         = nlaps,
            data_file        = self._data_file,
            tyre_temp_fl     = ttemps.get("fl"),
            tyre_temp_fr     = ttemps.get("fr"),
            tyre_temp_rl     = ttemps.get("rl"),
            tyre_temp_rr     = ttemps.get("rr"),
            tyre_psi_fl      = tpsi.get("fl"),
            tyre_psi_fr      = tpsi.get("fr"),
            tyre_psi_rl      = tpsi.get("rl"),
            tyre_psi_rr      = tpsi.get("rr"),
            brake_temp_fl    = self._brake["fl"].value(),
            brake_temp_fr    = self._brake["fr"].value(),
            brake_temp_rl    = self._brake["rl"].value(),
            brake_temp_rr    = self._brake["rr"].value(),
            motor_temp_c     = self._dt["motor_temp"].value(),
            controller_temp_c= self._dt["controller_temp"].value(),
            battery_temp_c   = self._dt["battery_temp"].value(),
            battery_voltage_v= self._dt["battery_voltage"].value(),
            battery_soc_pct  = self._dt["battery_soc"].value(),
            notes            = self._notes.toPlainText().strip(),
        )
        self._db.add(r)
        self._history_tab.refresh()
        QMessageBox.information(self.parent(), "Saved", "Telemetry reading saved.")

    def prefill_from_session(self, analysis):
        """Auto-fill best lap and # laps from a loaded session."""
        if analysis is None:
            return
        self._best_lap.setValue(analysis.best_lap.lap_time)
        self._num_laps.setValue(len(analysis.laps))


# ---------------------------------------------------------------------------
# History table
# ---------------------------------------------------------------------------

class _HistoryWidget(QWidget):
    COLS = ["Timestamp", "Session", "Track", "Best Lap",
            "Motor °C", "Batt V", "Batt °C",
            "T FL°C", "T FR°C", "T RL°C", "T RR°C",
            "PSI FL", "PSI FR", "PSI RL", "PSI RR",
            "Brk FL°C", "Brk FR°C"]

    def __init__(self, db: SessionDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)

        export_btn = QPushButton("Export CSV…")
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(export_btn)

        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.refresh()

    def refresh(self):
        readings = self._db.readings
        self.table.setRowCount(len(readings))
        for row, r in enumerate(readings):
            def _c(val, key=None):
                if val is None:
                    return "—"
                if isinstance(val, float):
                    return f"{val:.1f}"
                return str(val)

            def cell(text: str, thresh_key: str = "", value=None) -> QTableWidgetItem:
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if thresh_key and value is not None:
                    status = temp_status(value, thresh_key)
                    if status in ("warn_lo", "warn_hi"):
                        item.setForeground(QColor("#FFD700"))
                    elif status in ("danger_lo", "danger_hi"):
                        item.setForeground(QColor("#FF4444"))
                return item

            vals = [
                r.timestamp, r.session_type, r.track or "—",
                r.best_lap_str,
                _c(r.motor_temp_c), _c(r.battery_voltage_v), _c(r.battery_temp_c),
                _c(r.tyre_temp_fl), _c(r.tyre_temp_fr),
                _c(r.tyre_temp_rl), _c(r.tyre_temp_rr),
                _c(r.tyre_psi_fl),  _c(r.tyre_psi_fr),
                _c(r.tyre_psi_rl),  _c(r.tyre_psi_rr),
                _c(r.brake_temp_fl),_c(r.brake_temp_fr),
            ]
            thresh_keys = [
                "", "", "", "",
                "motor_temp", "battery_voltage", "battery_temp",
                "tyre_temp", "tyre_temp", "tyre_temp", "tyre_temp",
                "tyre_psi",  "tyre_psi",  "tyre_psi",  "tyre_psi",
                "brake_temp","brake_temp",
            ]
            raw_vals = [
                None, None, None, None,
                r.motor_temp_c, r.battery_voltage_v, r.battery_temp_c,
                r.tyre_temp_fl, r.tyre_temp_fr, r.tyre_temp_rl, r.tyre_temp_rr,
                r.tyre_psi_fl, r.tyre_psi_fr, r.tyre_psi_rl, r.tyre_psi_rr,
                r.brake_temp_fl, r.brake_temp_fr,
            ]
            for col, (txt, tkey, rval) in enumerate(zip(vals, thresh_keys, raw_vals)):
                self.table.setItem(row, col, cell(txt, tkey, rval))

        self.table.resizeColumnsToContents()

    def _delete(self):
        rows = sorted(set(i.row() for i in self.table.selectedItems()), reverse=True)
        for row in rows:
            self._db.remove(row)
        self.refresh()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Telemetry CSV", "telemetry_log.csv", "CSV (*.csv)"
        )
        if path:
            self._db.export_csv(path)
            QMessageBox.information(self, "Exported", f"Saved to {path}")


# ---------------------------------------------------------------------------
# Trends charts
# ---------------------------------------------------------------------------

class _TrendsWidget(QWidget):
    def __init__(self, db: SessionDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self.figure = Figure(facecolor=CHART_BG)
        layout = QVBoxLayout(self)

        refresh_btn = QPushButton("Refresh Trends")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

        self.canvas = FigureCanvasQTAgg(self.figure)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        toolbar.setStyleSheet("background-color: #0f3460;")
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)
        self.refresh()

    def refresh(self):
        self.figure.clear()
        readings = self._db.readings
        if len(readings) < 2:
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(CHART_BG)
            ax.text(0.5, 0.5, "Need ≥ 2 sessions to show trends",
                    ha="center", va="center", color="#888888",
                    transform=ax.transAxes, fontsize=13)
            self.canvas.draw_idle()
            return

        labels = [f"{r.timestamp[-8:-3]}\n{r.session_type[:8]}" for r in readings]
        x = np.arange(len(readings))

        specs = [
            ("Best Lap Time (s)", "best_lap_time_s", "#e94560", None),
            ("Motor Temp (°C)",   "motor_temp_c",    "#FF8800", 75),
            ("Battery Voltage (V)","battery_voltage_v","#00FF88", 45),
            ("Rear Tyre Avg Temp (°C)", None,         "#FFD700", 95),
        ]

        axes = self.figure.subplots(2, 2).flatten()
        for ax, (title, field, color, warn_val) in zip(axes, specs):
            ax.set_facecolor(CHART_BG)
            ax.tick_params(colors="#aaaacc", labelsize=7)
            for sp in ax.spines.values():
                sp.set_edgecolor("#333355")
            ax.grid(True, color=GRID_C, linewidth=0.5, linestyle="--")
            ax.set_title(title, color="#e0e0e0", fontsize=9, pad=4)

            if field:
                vals = [getattr(r, field) for r in readings]
                valid = [(xi, vi) for xi, vi in zip(x, vals) if vi is not None]
                if valid:
                    xs, ys = zip(*valid)
                    ax.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=5)
                    ax.set_xticks(list(xs))
                    ax.set_xticklabels(
                        [labels[i] for i in xs], color="#aaaacc", fontsize=6
                    )
            else:
                # Rear tyre avg
                vals = []
                for r in readings:
                    temps = [t for t in [r.tyre_temp_rl, r.tyre_temp_rr] if t is not None]
                    vals.append(float(np.mean(temps)) if temps else None)
                valid = [(xi, vi) for xi, vi in zip(x, vals) if vi is not None]
                if valid:
                    xs, ys = zip(*valid)
                    ax.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=5)
                    ax.set_xticks(list(xs))
                    ax.set_xticklabels(
                        [labels[i] for i in xs], color="#aaaacc", fontsize=6
                    )

            if warn_val is not None:
                ax.axhline(warn_val, color="#FF4444", linewidth=0.8,
                           linestyle="--", alpha=0.7, label="Limit")

        self.figure.tight_layout(pad=1.5)
        self.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Main Tab
# ---------------------------------------------------------------------------

class SessionLoggerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = SessionDatabase.load()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        self._history_widget = _HistoryWidget(self._db)
        self._trends_widget  = _TrendsWidget(self._db)
        self._new_widget     = _NewReadingWidget(self._db, self._history_widget)

        tabs.addTab(self._new_widget,     "New Reading")
        tabs.addTab(self._history_widget, "History")
        tabs.addTab(self._trends_widget,  "Trends")

        layout.addWidget(tabs)

    def prefill_from_session(self, analysis) -> None:
        self._new_widget.prefill_from_session(analysis)
