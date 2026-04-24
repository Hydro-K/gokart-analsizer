"""
Kart Performance Simulator Tab.

Takes actual driver data (speed trace, corner speeds, phases) and simulates
what the SAME driver would have done with different kart parameters:
  • Motor controller (max current, accel rate, speed limit)
  • Gear ratio (motor/axle sprocket teeth)
  • Tyre PSI (affects rolling resistance + corner grip)
  • Vehicle mass (kart or driver change)
  • Thermal effects (motor temp → effective current reduction)

Real-time: simulation reruns ~150 ms after any slider move.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QSlider, QSpinBox, QDoubleSpinBox, QPushButton,
    QSplitter, QTabWidget, QFrame, QSizePolicy, QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from scipy.ndimage import gaussian_filter1d

from src.alltrax_settings import AlltraxSettings
from src.gear_ratio import GearRatioConfig

if TYPE_CHECKING:
    from src.lap_analyzer import SessionAnalysis, LapData

CHART_BG = "#0d1b2a"
GRID_C   = "#1a2a3a"
ACT_COL  = "#00BFFF"
SIM_COL  = "#FF8800"
DELTA_POS = "#00FF88"
DELTA_NEG = "#FF4444"


# ---------------------------------------------------------------------------
# Physics helpers
# ---------------------------------------------------------------------------

def _simulate_lap(
    lap: "LapData",
    max_current: int,
    accel_rate: int,
    speed_limit_pct: int,
    gear_ratio_new: float,
    gear_ratio_old: float,
    mass_new_kg: float,
    mass_old_kg: float,
    tyre_psi_rear: float,
    tyre_psi_front: float,
    motor_temp_c: float,
) -> tuple[np.ndarray, float]:
    """
    Physics-based lap simulation anchored to actual driver data.

    Same-driver assumption: brake points, throttle application timing, and
    cornering lines are unchanged.  Only the kart's RESPONSE changes.

    Returns (simulated_speed_ms, simulated_lap_time_s).
    """
    from src.alltrax_settings import AlltraxSettings as AS
    from src.gear_ratio import GearRatioConfig as GRC

    time  = lap.time
    speed = lap.speed
    phase = lap.phase
    n     = len(time)

    dt = np.diff(time, prepend=time[0])
    dt[0] = dt[1] if len(dt) > 1 else 1 / 25.0
    dt = np.clip(dt, 1e-6, 1.0)

    smooth  = gaussian_filter1d(speed, sigma=5)
    accel_baseline = np.gradient(smooth, time)

    v_max_actual = float(np.max(smooth))

    # ---- 1. Current / torque scaling -----------------------------------
    base_current = 300  # nominal baseline for scaling
    current_scale = (max_current / base_current) ** 0.65

    # Motor thermal derating: above 70 °C resistance rises → less effective current
    thermal_factor = 1.0
    if motor_temp_c > 70:
        thermal_factor = max(0.6, 1.0 - (motor_temp_c - 70) * 0.004)
    current_scale *= thermal_factor

    accel_rate_scale = accel_rate / 64.0   # 64 is default

    # ---- 2. Gear ratio → top speed shift --------------------------------
    gear_scale = gear_ratio_old / gear_ratio_new   # >1 = higher top speed
    v_max_proj = v_max_actual * gear_scale
    speed_limit_ms = (speed_limit_pct / 100.0) * v_max_proj

    # ---- 3. Mass scaling ------------------------------------------------
    # Heavier → less acceleration (F=ma), more rolling resistance
    mass_ratio = mass_old_kg / max(mass_new_kg, 1.0)  # >1 = lighter = more accel

    # ---- 4. Tyre PSI effects -------------------------------------------
    # Rolling resistance: Cr ∝ 1/sqrt(PSI)
    psi_ref_rear  = 16.0   # PSI reference (optimal)
    psi_ref_front = 15.0
    cr_scale_rear  = (psi_ref_rear  / max(tyre_psi_rear,  1.0)) ** 0.3
    cr_scale_front = (psi_ref_front / max(tyre_psi_front, 1.0)) ** 0.3
    cr_scale = (cr_scale_rear + cr_scale_front) / 2.0  # avg

    # Lateral grip: peaks at reference PSI, drops off on either side
    def grip_factor(psi, psi_opt=16.0) -> float:
        deviation = abs(psi - psi_opt) / psi_opt
        return max(0.7, 1.0 - deviation ** 1.5 * 0.4)

    rear_grip  = grip_factor(tyre_psi_rear,  16.0)
    front_grip = grip_factor(tyre_psi_front, 15.0)
    avg_grip   = (rear_grip + front_grip) / 2.0

    # ---- 5. Build perturbation on top of actual trace ------------------
    delta_accel = np.zeros(n)
    for i in range(n):
        ph = str(phase[i])
        a  = float(accel_baseline[i])

        if ph == "accelerating" and a > 0:
            # Current / torque gain (with back-EMF rolloff near v_max)
            back_emf = max(0.0, 1.0 - smooth[i] / max(v_max_proj, 0.01))
            extra_cur  = (current_scale - 1.0) * a * back_emf
            extra_rate = (accel_rate_scale - 1.0) * a * 0.20 * back_emf
            # Mass benefit on acceleration
            extra_mass = (mass_ratio - 1.0) * a * 0.5
            # Rolling resistance drag change (lower cr = less drag = more accel)
            extra_cr   = (1.0 - cr_scale) * a * 0.15
            delta_accel[i] = extra_cur + extra_rate + extra_mass + extra_cr

        elif ph == "cornering":
            # Grip change → scale corner speed via apex perturbation
            # delta_v at cornering = (sqrt(new_grip) - 1) * current_corner_speed
            grip_delta = avg_grip - 1.0    # negative if underinflated past optimum
            delta_accel[i] = a * grip_delta * 0.5

        elif ph == "braking" and a < 0:
            # Mass affects braking distance; heavier = harder to stop
            extra_mass_brake = (1.0 - mass_ratio) * abs(a) * 0.3
            delta_accel[i] = -extra_mass_brake  # extra decel (more negative a = better)

    delta_v  = np.cumsum(delta_accel * dt)
    simulated = smooth + delta_v

    # Apply straight-speed scaling for gear ratio
    if abs(gear_scale - 1.0) > 0.001:
        ratio_arr    = smooth / max(v_max_actual, 0.01)
        gear_blend   = np.clip((ratio_arr - 0.70) / 0.30, 0.0, 1.0)
        simulated   += smooth * (gear_scale - 1.0) * gear_blend

    simulated = gaussian_filter1d(simulated, sigma=2)
    simulated = np.clip(simulated, 0.0, speed_limit_ms)

    # ---- 6. Estimate simulated lap time ---------------------------------
    cum_actual = np.cumsum(smooth * dt)
    total_dist = float(cum_actual[-1])
    cum_sim    = np.cumsum(simulated * dt)

    if cum_sim[-1] <= 0:
        sim_lap_time = lap.lap_time
    elif cum_sim[-1] < total_dist:
        sim_lap_time = lap.lap_time * (total_dist / float(cum_sim[-1]))
    else:
        sim_lap_time = float(np.interp(total_dist, cum_sim, time))

    return simulated, sim_lap_time


# ---------------------------------------------------------------------------
# Linked slider + spinbox helper (reused from settings_tab pattern)
# ---------------------------------------------------------------------------

class _LSpin(QWidget):
    value_changed = pyqtSignal(float)

    def __init__(self, label, mn, mx, default, step=1, is_float=False, suffix="", parent=None):
        super().__init__(parent)
        self._scale = 10 if is_float else 1
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFixedWidth(180)
        layout.addWidget(lbl)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(int(mn * self._scale), int(mx * self._scale))
        self.slider.setValue(int(default * self._scale))
        layout.addWidget(self.slider, 1)
        if is_float:
            self.spin = QDoubleSpinBox()
            self.spin.setRange(mn, mx)
            self.spin.setSingleStep(step)
            self.spin.setValue(default)
            self.spin.setDecimals(1)
            self.spin.setSuffix(suffix)
        else:
            self.spin = QSpinBox()
            self.spin.setRange(int(mn), int(mx))
            self.spin.setSingleStep(int(step))
            self.spin.setValue(int(default))
            self.spin.setSuffix(suffix)
        self.spin.setFixedWidth(90)
        layout.addWidget(self.spin)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _from_slider(self, v):
        real = v / self._scale
        self.spin.blockSignals(True)
        self.spin.setValue(real)
        self.spin.blockSignals(False)
        self.value_changed.emit(real)

    def _from_spin(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(int(float(v) * self._scale))
        self.slider.blockSignals(False)
        self.value_changed.emit(float(v))

    def get(self):
        return self.spin.value()

    def set(self, v):
        self.spin.blockSignals(True)
        self.slider.blockSignals(True)
        self.spin.setValue(v)
        self.slider.setValue(int(float(v) * self._scale))
        self.spin.blockSignals(False)
        self.slider.blockSignals(False)


# ---------------------------------------------------------------------------
# Main Tab
# ---------------------------------------------------------------------------

class SimulationTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional["SessionAnalysis"] = None
        self._base_gear = GearRatioConfig()
        self._base_settings = AlltraxSettings()
        self._sim_speed: Optional[np.ndarray] = None
        self._sim_lap_time: Optional[float] = None

        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self._run_simulation)

        self.figure = Figure(facecolor=CHART_BG)
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        hdr = QLabel("Kart Performance Simulator")
        hdr.setStyleSheet("font-size: 16px; font-weight: bold; color: #e94560; padding: 4px 0;")
        root.addWidget(hdr)

        sub = QLabel(
            "Predict lap time with the SAME driver, different kart configuration.  "
            "Changes update in real time."
        )
        sub.setStyleSheet("color: #8888aa; font-size: 11px; padding-bottom: 6px;")
        root.addWidget(sub)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # ---- Left: controls ----------------------------------------
        ctrl_scroll = QScrollArea()
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setFixedWidth(420)
        ctrl_scroll.setFrameShape(QFrame.NoFrame)
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setSpacing(8)
        ctrl_scroll.setWidget(ctrl_widget)

        # Powertrain
        pt = QGroupBox("Powertrain")
        ptl = QVBoxLayout(pt)
        self._w_current  = _LSpin("Max Current (A)", 100, 400, 300, suffix=" A")
        self._w_accel    = _LSpin("Accel Rate (1-255)", 1, 255, 64)
        self._w_speed_lim= _LSpin("Speed Limit (%)", 10, 100, 100, suffix="%")
        self._w_motor_sp = _LSpin("Motor Sprocket (T)", 6, 30, 11)
        self._w_axle_sp  = _LSpin("Axle Sprocket (T)", 30, 150, 72)

        self._ratio_lbl  = QLabel("Ratio: 6.55:1  |  Est. top speed: — km/h")
        self._ratio_lbl.setStyleSheet("color: #FFD700; font-size: 11px; padding: 2px 0;")

        for w in (self._w_current, self._w_accel, self._w_speed_lim,
                  self._w_motor_sp, self._w_axle_sp):
            ptl.addWidget(w)
            w.value_changed.connect(self._on_change)
        self._w_motor_sp.value_changed.connect(self._update_ratio_label)
        self._w_axle_sp.value_changed.connect(self._update_ratio_label)
        ptl.addWidget(self._ratio_lbl)
        ctrl_layout.addWidget(pt)

        # Tyres
        tg = QGroupBox("Tyre Pressures  (PSI — affects rolling resistance & grip)")
        tgl = QGridLayout(tg)
        self._w_psi = {}
        for row, (corner, lbl) in enumerate([("fl","Front Left"),("fr","Front Right"),
                                              ("rl","Rear Left"), ("rr","Rear Right")]):
            tgl.addWidget(QLabel(lbl+":"), row, 0)
            sp = QDoubleSpinBox()
            sp.setRange(8.0, 25.0)
            sp.setSingleStep(0.5)
            sp.setValue(16.0)
            sp.setSuffix(" PSI")
            sp.valueChanged.connect(self._on_change)
            tgl.addWidget(sp, row, 1)
            self._w_psi[corner] = sp
        ctrl_layout.addWidget(tg)

        # Vehicle mass
        mg = QGroupBox("Vehicle Mass")
        mgl = QGridLayout(mg)
        mgl.addWidget(QLabel("Kart mass (kg):"), 0, 0)
        self._w_kart_mass = QDoubleSpinBox()
        self._w_kart_mass.setRange(50, 200)
        self._w_kart_mass.setValue(115)
        self._w_kart_mass.setSuffix(" kg")
        self._w_kart_mass.valueChanged.connect(self._on_change)
        mgl.addWidget(self._w_kart_mass, 0, 1)

        mgl.addWidget(QLabel("Driver mass (kg):"), 1, 0)
        self._w_driver_mass = QDoubleSpinBox()
        self._w_driver_mass.setRange(40, 150)
        self._w_driver_mass.setValue(70)
        self._w_driver_mass.setSuffix(" kg")
        self._w_driver_mass.valueChanged.connect(self._on_change)
        mgl.addWidget(self._w_driver_mass, 1, 1)

        self._mass_total_lbl = QLabel("Total: 185 kg")
        self._mass_total_lbl.setStyleSheet("color: #aaaacc;")
        mgl.addWidget(self._mass_total_lbl, 2, 0, 1, 2)
        self._w_kart_mass.valueChanged.connect(self._update_mass_label)
        self._w_driver_mass.valueChanged.connect(self._update_mass_label)
        ctrl_layout.addWidget(mg)

        # Thermal
        thg = QGroupBox("Thermal Conditions")
        thgl = QGridLayout(thg)
        thgl.addWidget(QLabel("Motor temp (°C):"), 0, 0)
        self._w_motor_temp = QDoubleSpinBox()
        self._w_motor_temp.setRange(10, 150)
        self._w_motor_temp.setValue(40)
        self._w_motor_temp.setSuffix(" °C")
        self._w_motor_temp.valueChanged.connect(self._on_change)
        thgl.addWidget(self._w_motor_temp, 0, 1)

        self._motor_temp_warn = QLabel("")
        thgl.addWidget(self._motor_temp_warn, 1, 0, 1, 2)
        self._w_motor_temp.valueChanged.connect(self._update_temp_warn)
        ctrl_layout.addWidget(thg)

        # Action row
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to Actual")
        reset_btn.clicked.connect(self._reset_to_actual)
        btn_row.addWidget(reset_btn)
        run_btn = QPushButton("Run Simulation")
        run_btn.setStyleSheet("background-color: #e94560; font-weight: bold;")
        run_btn.clicked.connect(self._run_simulation)
        btn_row.addWidget(run_btn)
        ctrl_layout.addLayout(btn_row)
        ctrl_layout.addStretch()

        splitter.addWidget(ctrl_scroll)

        # ---- Right: results -----------------------------------------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Headline result
        self._result_lbl = QLabel("Load a session to run simulation")
        self._result_lbl.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #e94560; "
            "padding: 8px; border: 1px solid #333355; border-radius: 6px;"
        )
        self._result_lbl.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self._result_lbl)

        # Charts
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        toolbar.setStyleSheet("background-color: #0f3460; color: #e0e0e0;")
        right_layout.addWidget(toolbar)
        right_layout.addWidget(self.canvas)

        # Breakdown table
        self._breakdown_lbl = QLabel("")
        self._breakdown_lbl.setStyleSheet(
            "background-color: #0d1b2a; border: 1px solid #333355; "
            "border-radius: 4px; padding: 8px; font-family: monospace; color: #e0e0e0; font-size: 11px;"
        )
        self._breakdown_lbl.setWordWrap(True)
        right_layout.addWidget(self._breakdown_lbl)

        splitter.addWidget(right)
        splitter.setSizes([420, 900])

        self._update_ratio_label()
        self._update_mass_label()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_change(self, _=None):
        self._timer.start()

    def _update_ratio_label(self, _=None):
        motor_t = int(self._w_motor_sp.get())
        axle_t  = int(self._w_axle_sp.get())
        ratio   = axle_t / max(1, motor_t)
        if self.session is not None:
            v_max_obs = self.session.best_lap.max_speed_kmh
            # Scale from base config
            if self._base_gear.ratio > 0:
                v_top = v_max_obs * (self._base_gear.ratio / ratio)
            else:
                g = GearRatioConfig(motor_sprocket_teeth=motor_t, axle_sprocket_teeth=axle_t)
                v_top = g.top_speed_kmh()
            self._ratio_lbl.setText(
                f"Ratio: {ratio:.2f}:1  |  Est. top speed: {v_top:.1f} km/h"
            )
        else:
            self._ratio_lbl.setText(f"Ratio: {ratio:.2f}:1")

    def _update_mass_label(self, _=None):
        total = self._w_kart_mass.value() + self._w_driver_mass.value()
        self._mass_total_lbl.setText(f"Total: {total:.0f} kg")
        self._on_change()

    def _update_temp_warn(self, v):
        if v > 95:
            self._motor_temp_warn.setText("⚠ Danger: motor may derate significantly")
            self._motor_temp_warn.setStyleSheet("color: #FF4444;")
        elif v > 70:
            self._motor_temp_warn.setText("⚠ Elevated: slight efficiency loss (~{:.0f}%)".format((v-70)*0.4))
            self._motor_temp_warn.setStyleSheet("color: #FFD700;")
        else:
            self._motor_temp_warn.setText("✓ Normal operating range")
            self._motor_temp_warn.setStyleSheet("color: #00FF88;")
        self._on_change()

    def _reset_to_actual(self):
        """Reset all controls to the values loaded from the actual session."""
        s = self._base_settings
        g = self._base_gear
        self._w_current.set(s.max_current)
        self._w_accel.set(s.accel_rate)
        self._w_speed_lim.set(s.speed_limit)
        self._w_motor_sp.set(g.motor_sprocket_teeth)
        self._w_axle_sp.set(g.axle_sprocket_teeth)
        for corner in ("fl", "fr", "rl", "rr"):
            self._w_psi[corner].setValue(16.0)
        self._w_kart_mass.setValue(115)
        self._w_driver_mass.setValue(70)
        self._w_motor_temp.setValue(40)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def set_session(self, analysis: "SessionAnalysis") -> None:
        self.session = analysis
        self._update_ratio_label()
        self._run_simulation()

    def set_base_settings(self, settings: AlltraxSettings, gear: GearRatioConfig) -> None:
        self._base_settings = settings
        self._base_gear = gear
        self._w_current.set(settings.max_current)
        self._w_accel.set(settings.accel_rate)
        self._w_speed_lim.set(settings.speed_limit)
        self._w_motor_sp.set(gear.motor_sprocket_teeth)
        self._w_axle_sp.set(gear.axle_sprocket_teeth)

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def _run_simulation(self):
        if self.session is None:
            return

        lap = self.session.best_lap
        base_gear_ratio = self._base_gear.ratio if self._base_gear.ratio > 0 else 6.55
        new_motor_t = int(self._w_motor_sp.get())
        new_axle_t  = int(self._w_axle_sp.get())
        new_ratio   = new_axle_t / max(1, new_motor_t)

        try:
            sim_speed, sim_time = _simulate_lap(
                lap=lap,
                max_current=int(self._w_current.get()),
                accel_rate=int(self._w_accel.get()),
                speed_limit_pct=int(self._w_speed_lim.get()),
                gear_ratio_new=new_ratio,
                gear_ratio_old=base_gear_ratio,
                mass_new_kg=self._w_kart_mass.value() + self._w_driver_mass.value(),
                mass_old_kg=185.0,
                tyre_psi_rear=self._w_psi["rl"].value(),
                tyre_psi_front=self._w_psi["fl"].value(),
                motor_temp_c=self._w_motor_temp.value(),
            )
        except Exception as exc:
            self._result_lbl.setText(f"Simulation error: {exc}")
            return

        self._sim_speed    = sim_speed
        self._sim_lap_time = sim_time

        delta = sim_time - lap.lap_time
        sign  = "+" if delta >= 0 else ""
        color = DELTA_NEG if delta >= 0 else DELTA_POS
        self._result_lbl.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {color}; "
            "padding: 8px; border: 1px solid #333355; border-radius: 6px;"
        )
        self._result_lbl.setText(
            f"Predicted lap time: {self._fmt(sim_time)}   "
            f"({'faster' if delta < 0 else 'slower'}: {sign}{abs(delta):.3f}s)"
        )

        self._build_breakdown(lap, sim_speed, sim_time, delta)
        self._draw(lap, sim_speed)

    def _fmt(self, t: float) -> str:
        m = int(t // 60)
        s = t % 60
        return f"{m}:{s:06.3f}"

    def _build_breakdown(self, lap, sim_speed, sim_time, delta):
        actual_t  = lap.lap_time
        top_act   = float(np.max(lap.speed)) * 3.6
        top_sim   = float(np.max(sim_speed)) * 3.6
        avg_act   = float(np.mean(lap.speed)) * 3.6
        avg_sim   = float(np.mean(sim_speed)) * 3.6

        lines = [
            f"{'Parameter':<25} {'Actual':>10} {'Simulated':>12} {'Delta':>10}",
            "─" * 60,
            f"{'Lap time':<25} {self._fmt(actual_t):>10} {self._fmt(sim_time):>12} "
            f"{ ('+' if delta>=0 else '') + f'{delta:.3f}s':>10}",
            f"{'Top speed':<25} {top_act:>9.1f} km/h {top_sim:>10.1f} km/h "
            f"{ ('+' if top_sim-top_act>=0 else '') + f'{top_sim-top_act:.1f} km/h':>10}",
            f"{'Avg speed':<25} {avg_act:>9.1f} km/h {avg_sim:>10.1f} km/h "
            f"{ ('+' if avg_sim-avg_act>=0 else '') + f'{avg_sim-avg_act:.1f} km/h':>10}",
        ]
        self._breakdown_lbl.setText("\n".join(lines))

    def _draw(self, lap, sim_speed):
        self.figure.clear()
        gs = GridSpec(2, 1, figure=self.figure, height_ratios=[3, 1], hspace=0.35)
        ax_trace = self.figure.add_subplot(gs[0])
        ax_delta = self.figure.add_subplot(gs[1])

        for ax in (ax_trace, ax_delta):
            ax.set_facecolor(CHART_BG)
            ax.tick_params(colors="#aaaacc", labelsize=8)
            ax.xaxis.label.set_color("#aaaacc")
            ax.yaxis.label.set_color("#aaaacc")
            for spine in ax.spines.values():
                spine.set_edgecolor("#333355")
            ax.grid(True, color=GRID_C, linewidth=0.5, linestyle="--")

        time = lap.time
        act_kmh = lap.speed * 3.6
        sim_kmh = sim_speed * 3.6

        ax_trace.plot(time, act_kmh, color=ACT_COL, linewidth=2.0,
                      label=f"Actual ({lap.lap_time_str})", zorder=3)
        ax_trace.plot(time, sim_kmh, color=SIM_COL, linewidth=2.0,
                      linestyle="--", label=f"Simulated ({self._fmt(self._sim_lap_time)})",
                      zorder=4)

        # Corner apex markers
        for c in lap.corners:
            ax_trace.axvline(c.apex_time, color="#FFD700", linewidth=0.5,
                             alpha=0.4, linestyle=":")

        ax_trace.fill_between(time, act_kmh, sim_kmh,
                              where=(sim_kmh > act_kmh), color=DELTA_POS, alpha=0.18,
                              label="Sim faster here")
        ax_trace.fill_between(time, act_kmh, sim_kmh,
                              where=(sim_kmh < act_kmh), color=DELTA_NEG, alpha=0.18,
                              label="Sim slower here")
        ax_trace.set_ylabel("Speed (km/h)", color="#aaaacc")
        ax_trace.set_title("Actual vs Simulated Speed Trace", color="#e0e0e0", fontsize=10)
        ax_trace.legend(facecolor="#0d1b2a", edgecolor="#333355",
                        labelcolor="#e0e0e0", fontsize=8)

        # Speed delta
        delta = sim_kmh - act_kmh
        ax_delta.axhline(0, color="#555577", linewidth=0.8)
        ax_delta.fill_between(time, delta, 0,
                              where=(delta >= 0), color=DELTA_POS, alpha=0.4)
        ax_delta.fill_between(time, delta, 0,
                              where=(delta < 0), color=DELTA_NEG, alpha=0.4)
        ax_delta.plot(time, delta, color="#FFFFFF", linewidth=0.7, alpha=0.5)
        ax_delta.set_ylabel("Δ Speed (km/h)", color="#aaaacc")
        ax_delta.set_xlabel("Time (s)", color="#aaaacc")

        self.canvas.draw_idle()

    def _on_scroll(self, event):
        if event.inaxes is None:
            return
        scale = 0.85 if event.button == "up" else 1.15
        ax = event.inaxes
        xd, yd = event.xdata, event.ydata
        ax.set_xlim([xd + (x - xd) * scale for x in ax.get_xlim()])
        ax.set_ylim([yd + (y - yd) * scale for y in ax.get_ylim()])
        self.canvas.draw_idle()
