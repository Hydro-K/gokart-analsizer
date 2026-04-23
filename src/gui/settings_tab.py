"""
Settings tab: Alltrax SR-72400 parameters, gear ratio calculator,
and 10-point draggable throttle curve editor.
Emits settings_changed signal on any change for real-time projection updates.
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QSlider, QSpinBox, QDoubleSpinBox, QCheckBox,
    QPushButton, QComboBox, QSizePolicy, QScrollArea, QFrame,
    QSplitter,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from src.alltrax_settings import AlltraxSettings
from src.gear_ratio import GearRatioConfig
from src.setup_log import SetupLog

if TYPE_CHECKING:
    from src.recommendations import Recommendation

CHART_BG = "#0d1b2a"


class _LinkedSliderSpin(QWidget):
    """Horizontal slider + spinbox that stay in sync."""
    value_changed = pyqtSignal(float)

    def __init__(
        self, label: str, minimum, maximum, default, step=1,
        is_float=False, parent=None,
    ):
        super().__init__(parent)
        self._is_float = is_float
        self._scale = 10 if is_float else 1
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label)
        lbl.setFixedWidth(160)
        layout.addWidget(lbl)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(int(minimum * self._scale))
        self.slider.setMaximum(int(maximum * self._scale))
        self.slider.setValue(int(default * self._scale))
        layout.addWidget(self.slider, 1)

        if is_float:
            self.spin = QDoubleSpinBox()
            self.spin.setMinimum(minimum)
            self.spin.setMaximum(maximum)
            self.spin.setSingleStep(step)
            self.spin.setValue(default)
            self.spin.setDecimals(1)
        else:
            self.spin = QSpinBox()
            self.spin.setMinimum(int(minimum))
            self.spin.setMaximum(int(maximum))
            self.spin.setSingleStep(int(step))
            self.spin.setValue(int(default))
        self.spin.setFixedWidth(80)
        layout.addWidget(self.spin)

        self.slider.valueChanged.connect(self._slider_changed)
        self.spin.valueChanged.connect(self._spin_changed)

    def _slider_changed(self, v):
        real = v / self._scale
        self.spin.blockSignals(True)
        if self._is_float:
            self.spin.setValue(real)
        else:
            self.spin.setValue(int(real))
        self.spin.blockSignals(False)
        self.value_changed.emit(real)

    def _spin_changed(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(int(float(v) * self._scale))
        self.slider.blockSignals(False)
        self.value_changed.emit(float(v))

    def get_value(self):
        if self._is_float:
            return self.spin.value()
        return int(self.spin.value())

    def set_value(self, v):
        self.spin.blockSignals(True)
        self.slider.blockSignals(True)
        if self._is_float:
            self.spin.setValue(float(v))
        else:
            self.spin.setValue(int(v))
        self.slider.setValue(int(float(v) * self._scale))
        self.spin.blockSignals(False)
        self.slider.blockSignals(False)


class _ThrottleCurveEditor(QWidget):
    """10-point draggable throttle curve on a matplotlib canvas."""
    curve_changed = pyqtSignal(list)  # list of 11 float values

    def __init__(self, parent=None):
        super().__init__(parent)
        # 11 points: index 0-10 → throttle input 0, 10, 20, ..., 100%
        self._x = np.arange(0, 101, 10, dtype=float)
        self._y = self._x.copy()  # linear default
        self._dragging: Optional[int] = None
        self._pick_radius = 8  # points in data coords

        self.figure = Figure(figsize=(4, 3), facecolor=CHART_BG)
        self.ax = self.figure.add_subplot(111)
        self._style_ax()

        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(220)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self._draw()

    def _style_ax(self):
        ax = self.ax
        ax.set_facecolor(CHART_BG)
        ax.tick_params(colors="#aaaacc", labelsize=8)
        ax.xaxis.label.set_color("#aaaacc")
        ax.yaxis.label.set_color("#aaaacc")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")
        ax.grid(True, color="#1a2a3a", linewidth=0.5, linestyle="--")
        ax.set_xlabel("Throttle Input (%)")
        ax.set_ylabel("Motor Output (%)")
        ax.set_xlim(-2, 102)
        ax.set_ylim(-2, 102)

    def _draw(self):
        self.ax.cla()
        self._style_ax()
        # Reference line
        self.ax.plot([0, 100], [0, 100], color="#333355", linewidth=1, linestyle="--")
        # Curve
        self.ax.plot(self._x, self._y, color="#e94560", linewidth=2, zorder=3)
        # Draggable points
        self.ax.scatter(self._x, self._y, color="#FFD700", s=60, zorder=5)
        self.ax.set_title("Throttle Curve", color="#e0e0e0", fontsize=9, pad=4)
        self.canvas.draw_idle()

    def set_curve(self, values: list):
        self._y = np.array(values[:11], dtype=float)
        self._draw()

    def get_curve(self) -> list:
        return self._y.tolist()

    def _nearest_point(self, xd, yd):
        if xd is None:
            return None
        dists = np.sqrt((self._x - xd) ** 2 + (self._y - yd) ** 2)
        idx = int(np.argmin(dists))
        if dists[idx] < 15:
            return idx
        return None

    def _on_press(self, event):
        if event.inaxes != self.ax:
            return
        self._dragging = self._nearest_point(event.xdata, event.ydata)

    def _on_motion(self, event):
        if self._dragging is None or event.inaxes != self.ax:
            return
        new_y = float(np.clip(event.ydata, 0, 100))
        self._y[self._dragging] = new_y
        # Enforce monotonicity (optional but good UX)
        # self._y = np.maximum.accumulate(self._y)  # uncomment if desired
        self._draw()

    def _on_release(self, event):
        if self._dragging is not None:
            self.curve_changed.emit(self._y.tolist())
        self._dragging = None


class SettingsTab(QWidget):
    settings_changed = pyqtSignal(object, object)  # AlltraxSettings, GearRatioConfig

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = AlltraxSettings()
        self._gear = GearRatioConfig()
        self._emit_timer = QTimer()
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(150)  # debounce 150ms for real-time feel
        self._emit_timer.timeout.connect(self._emit_settings)
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left: Alltrax + Gear Ratio
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(8)
        splitter.addWidget(left)

        # Right: Throttle curve
        right = QWidget()
        right_layout = QVBoxLayout(right)
        splitter.addWidget(right)
        splitter.setSizes([700, 350])

        # ---- Alltrax Settings ------------------------------------------
        alltrax_group = QGroupBox("Alltrax SR-72400 Settings")
        alltrax_layout = QVBoxLayout(alltrax_group)

        s = self._settings
        self._max_current = _LinkedSliderSpin("Max Current (A)", 0, 400, s.max_current)
        self._accel_rate = _LinkedSliderSpin("Accel Rate (1–255)", 1, 255, s.accel_rate)
        self._decel_rate = _LinkedSliderSpin("Decel/Plug Brake Rate", 1, 255, s.decel_rate)
        self._speed_limit = _LinkedSliderSpin("Speed Limit (%)", 0, 100, s.speed_limit)
        self._lo_volt = _LinkedSliderSpin("Lo Voltage Cutoff (V)", 20.0, 50.0, s.lo_voltage_cutoff,
                                          step=0.5, is_float=True)
        self._hi_volt = _LinkedSliderSpin("Hi Voltage Cutoff (V)", 40.0, 70.0, s.hi_voltage_cutoff,
                                          step=0.5, is_float=True)
        self._deadband = _LinkedSliderSpin("Throttle Deadband (0–255)", 0, 255, s.throttle_deadband)
        self._regen_intensity = _LinkedSliderSpin("Regen Intensity (%)", 0, 100, s.regen_intensity)

        for w in (self._max_current, self._accel_rate, self._decel_rate, self._speed_limit,
                  self._lo_volt, self._hi_volt, self._deadband, self._regen_intensity):
            alltrax_layout.addWidget(w)
            w.value_changed.connect(self._on_any_change)

        bool_row = QHBoxLayout()
        self._peak_amp_cb = QCheckBox("Peak Amp Mode")
        self._peak_amp_cb.setChecked(s.peak_amp_mode)
        self._peak_amp_cb.toggled.connect(self._on_any_change)
        bool_row.addWidget(self._peak_amp_cb)

        self._regen_cb = QCheckBox("Regen Braking")
        self._regen_cb.setChecked(s.regen_braking)
        self._regen_cb.toggled.connect(self._on_any_change)
        bool_row.addWidget(self._regen_cb)
        bool_row.addStretch()
        alltrax_layout.addLayout(bool_row)

        # Action buttons
        btn_row = QHBoxLayout()
        self._apply_rec_btn = QPushButton("Apply Recommendations")
        self._apply_rec_btn.setStyleSheet("background-color: #e94560; font-weight: bold;")
        self._apply_rec_btn.clicked.connect(self._request_apply_recs)
        btn_row.addWidget(self._apply_rec_btn)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)
        alltrax_layout.addLayout(btn_row)

        left_layout.addWidget(alltrax_group)

        # ---- Gear Ratio ------------------------------------------------
        gear_group = QGroupBox("Gear Ratio & Top Speed")
        gear_layout = QGridLayout(gear_group)

        g = self._gear
        gear_layout.addWidget(QLabel("Motor sprocket (teeth):"), 0, 0)
        self._motor_teeth = QSpinBox()
        self._motor_teeth.setRange(6, 50)
        self._motor_teeth.setValue(g.motor_sprocket_teeth)
        self._motor_teeth.valueChanged.connect(self._on_gear_change)
        gear_layout.addWidget(self._motor_teeth, 0, 1)

        gear_layout.addWidget(QLabel("Axle sprocket (teeth):"), 1, 0)
        self._axle_teeth = QSpinBox()
        self._axle_teeth.setRange(30, 150)
        self._axle_teeth.setValue(g.axle_sprocket_teeth)
        self._axle_teeth.valueChanged.connect(self._on_gear_change)
        gear_layout.addWidget(self._axle_teeth, 1, 1)

        gear_layout.addWidget(QLabel("Tire diameter (in):"), 2, 0)
        self._tire_dia = QDoubleSpinBox()
        self._tire_dia.setRange(6.0, 20.0)
        self._tire_dia.setSingleStep(0.5)
        self._tire_dia.setValue(g.tire_diameter_in)
        self._tire_dia.valueChanged.connect(self._on_gear_change)
        gear_layout.addWidget(self._tire_dia, 2, 1)

        gear_layout.addWidget(QLabel("Motor max RPM (est.):"), 3, 0)
        self._motor_rpm = QSpinBox()
        self._motor_rpm.setRange(1000, 12000)
        self._motor_rpm.setSingleStep(100)
        self._motor_rpm.setValue(g.motor_rpm_max)
        self._motor_rpm.valueChanged.connect(self._on_gear_change)
        gear_layout.addWidget(self._motor_rpm, 3, 1)

        gear_layout.addWidget(QLabel("Reduction ratio:"), 4, 0)
        self._ratio_label = QLabel(f"{g.ratio:.2f}:1")
        self._ratio_label.setStyleSheet("color: #FFD700; font-weight: bold;")
        gear_layout.addWidget(self._ratio_label, 4, 1)

        gear_layout.addWidget(QLabel("Theoretical top speed:"), 5, 0)
        self._top_speed_label = QLabel(f"{g.top_speed_kmh():.1f} km/h")
        self._top_speed_label.setStyleSheet("color: #00FF88; font-weight: bold;")
        gear_layout.addWidget(self._top_speed_label, 5, 1)

        left_layout.addWidget(gear_group)
        left_layout.addStretch()

        # ---- Throttle Curve ----------------------------------------
        curve_group = QGroupBox("Throttle Curve Editor")
        curve_layout = QVBoxLayout(curve_group)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(AlltraxSettings.THROTTLE_PRESETS.keys())
        self._preset_combo.currentTextChanged.connect(self._apply_preset)
        preset_row.addWidget(self._preset_combo)
        preset_row.addStretch()
        curve_layout.addLayout(preset_row)

        self._curve_editor = _ThrottleCurveEditor()
        self._curve_editor.set_curve(self._settings.throttle_curve)
        self._curve_editor.curve_changed.connect(self._on_curve_changed)
        curve_layout.addWidget(self._curve_editor)

        right_layout.addWidget(curve_group)
        right_layout.addStretch()

    # ------------------------------------------------------------------
    # Change handlers
    # ------------------------------------------------------------------

    def _on_any_change(self, *args):
        self._sync_settings()
        self._emit_timer.start()

    def _on_gear_change(self, *args):
        self._sync_gear()
        self._ratio_label.setText(f"{self._gear.ratio:.2f}:1")
        self._top_speed_label.setText(f"{self._gear.top_speed_kmh():.1f} km/h")
        self._emit_timer.start()

    def _on_curve_changed(self, values: list):
        self._settings.throttle_curve = values
        self._emit_timer.start()

    def _apply_preset(self, name: str):
        if name in AlltraxSettings.THROTTLE_PRESETS:
            self._curve_editor.set_curve(AlltraxSettings.THROTTLE_PRESETS[name])
            self._settings.throttle_curve = AlltraxSettings.THROTTLE_PRESETS[name]
            self._emit_timer.start()

    def _sync_settings(self):
        s = self._settings
        s.max_current = self._max_current.get_value()
        s.accel_rate = self._accel_rate.get_value()
        s.decel_rate = self._decel_rate.get_value()
        s.speed_limit = self._speed_limit.get_value()
        s.lo_voltage_cutoff = self._lo_volt.get_value()
        s.hi_voltage_cutoff = self._hi_volt.get_value()
        s.throttle_deadband = self._deadband.get_value()
        s.regen_intensity = self._regen_intensity.get_value()
        s.peak_amp_mode = self._peak_amp_cb.isChecked()
        s.regen_braking = self._regen_cb.isChecked()

    def _sync_gear(self):
        g = self._gear
        g.motor_sprocket_teeth = self._motor_teeth.value()
        g.axle_sprocket_teeth = self._axle_teeth.value()
        g.tire_diameter_in = self._tire_dia.value()
        g.motor_rpm_max = self._motor_rpm.value()

    def _emit_settings(self):
        self.settings_changed.emit(self._settings, self._gear)

    def _reset_defaults(self):
        s = AlltraxSettings()
        self.load_settings(s)

    def _request_apply_recs(self):
        # Tell MainWindow to apply current recommendations
        mw = self.parent()
        if hasattr(mw, "_apply_recommendations"):
            mw._apply_recommendations(getattr(mw, "recommendations", []))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_settings(self, s: AlltraxSettings):
        self._settings = s
        self._max_current.set_value(s.max_current)
        self._accel_rate.set_value(s.accel_rate)
        self._decel_rate.set_value(s.decel_rate)
        self._speed_limit.set_value(s.speed_limit)
        self._lo_volt.set_value(s.lo_voltage_cutoff)
        self._hi_volt.set_value(s.hi_voltage_cutoff)
        self._deadband.set_value(s.throttle_deadband)
        self._regen_intensity.set_value(s.regen_intensity)
        self._peak_amp_cb.setChecked(s.peak_amp_mode)
        self._regen_cb.setChecked(s.regen_braking)
        self._curve_editor.set_curve(s.throttle_curve)
        self._emit_settings()

    def apply_recommendations(
        self, recs: List["Recommendation"], setup_log: SetupLog
    ):
        for rec in recs:
            if not rec.setting_key or rec.delta == 0:
                continue
            key = rec.setting_key
            old = getattr(self._settings, key, None)
            if old is None:
                old = getattr(self._gear, key, None)
                if old is None:
                    continue
                new_val = type(old)(old + rec.delta)
                setup_log.record(rec.parameter, old, new_val)
                setattr(self._gear, key, new_val)
            else:
                if isinstance(old, bool):
                    new_val = bool(rec.delta)
                else:
                    new_val = type(old)(old + rec.delta)
                setup_log.record(rec.parameter, old, new_val)
                setattr(self._settings, key, new_val)

        self.load_settings(self._settings)
        self._on_gear_change()

    def get_settings(self) -> tuple[AlltraxSettings, GearRatioConfig]:
        return self._settings, self._gear
