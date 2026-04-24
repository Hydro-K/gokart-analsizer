"""
Rules & Compliance Tab — Purdue EV Grand Prix 2025-26.

Shows every rule limit, checks current settings, and highlights violations
in red.  All limits are editable so the team can update them without a code
change when the governing body publishes revised rules.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QScrollArea, QDoubleSpinBox, QFormLayout, QDialog,
    QDialogButtonBox, QTextEdit, QSplitter, QFrame, QTabWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from src.competition_rules import (
    CompetitionRules, ComplianceChecker, ComplianceReport,
    ComplianceItem, get_rules, set_rules,
)

if TYPE_CHECKING:
    from src.alltrax_settings import AlltraxSettings
    from src.gear_ratio import GearRatioConfig

# Status colours
_COL = {
    "PASS":   ("#00cc66", "#003311"),
    "WARN":   ("#FFD700", "#332200"),
    "FAIL":   ("#ff4444", "#330000"),
    "VERIFY": ("#88aaff", "#001133"),
}


def _status_icon(status: str) -> str:
    return {"PASS": "✅", "WARN": "⚠", "FAIL": "⛔", "VERIFY": "ℹ"}.get(status, "?")


# ---------------------------------------------------------------------------
# Edit-limits dialog
# ---------------------------------------------------------------------------

class _EditLimitsDialog(QDialog):
    """Allow the team to update any numeric rule limit."""

    def __init__(self, rules: CompetitionRules, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Competition Rule Limits")
        self.setMinimumWidth(560)
        self.rules = rules
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        note = QLabel(
            "⚠  Edit these values to match the official 2025-26 rulebook.\n"
            "Changes are saved to ~/.evkart_rules.json and apply immediately."
        )
        note.setStyleSheet(
            "background:#332200; color:#FFD700; padding:8px; "
            "border-radius:4px; font-size:12px;"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setLabelAlignment(Qt.AlignRight)

        def _add(label: str, attr: str, lo: float, hi: float, decimals: int = 1, suffix: str = "") -> None:
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setDecimals(decimals)
            spin.setSuffix(f"  {suffix}" if suffix else "")
            spin.setValue(getattr(self.rules, attr))
            self._spins[attr] = spin
            form.addRow(label, spin)

        form.addRow(_section("Battery (LiFePO4)"))
        _add("Nominal voltage",        "battery_voltage_nominal_v",  30, 100, 1, "V")
        _add("Max charge voltage",     "battery_voltage_max_v",      30, 100, 1, "V")
        _add("Min discharge voltage",  "battery_voltage_min_v",      10,  80, 1, "V")
        _add("Capacity",               "battery_capacity_wh",       100,9999, 0, "Wh")
        _add("BMS max current",        "battery_bms_max_current_a",  10, 500, 0, "A")

        form.addRow(_section("Controller"))
        _add("Max current (rule limit)", "controller_max_current_a",  10, 600, 0, "A")
        _add("Hi-cutoff max allowed",    "controller_hi_cutoff_max_v", 30, 100, 1, "V")
        _add("Lo-cutoff min allowed",    "controller_lo_cutoff_min_v", 10,  80, 1, "V")

        form.addRow(_section("Performance"))
        _add("Speed limit",    "speed_limit_kmh",        20, 200, 0, "km/h")

        form.addRow(_section("Tyres"))
        _add("Min tyre pressure", "tyre_pressure_min_psi",  5, 50, 0, "PSI")
        _add("Max tyre pressure", "tyre_pressure_max_psi",  5, 50, 0, "PSI")

        form.addRow(_section("Weight"))
        _add("Min combined weight (kart+driver)", "combined_min_weight_kg", 50, 500, 1, "kg")

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_updated_rules(self) -> CompetitionRules:
        r = CompetitionRules(**{k: v.value() for k, v in self._spins.items()})
        r.rulebook_version = self.rules.rulebook_version
        r.notes = self.rules.notes
        r.controller_allowed_models = self.rules.controller_allowed_models
        r.tyre_compound = self.rules.tyre_compound
        r.tyre_front_size = self.rules.tyre_front_size
        r.tyre_rear_size = self.rules.tyre_rear_size
        r.chassis_required = self.rules.chassis_required
        return r


def _section(title: str) -> QLabel:
    lbl = QLabel(f"── {title} ──")
    lbl.setStyleSheet("color:#aaaaee; font-weight:bold; margin-top:8px;")
    return lbl


# ---------------------------------------------------------------------------
# Compliance table
# ---------------------------------------------------------------------------

class _ComplianceTable(QTableWidget):
    item_selected = pyqtSignal(ComplianceItem)

    _HEADERS = ["Status", "Rule", "Your Value", "Limit", "Section"]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(0, len(self._HEADERS), parent)
        self.setHorizontalHeaderLabels(self._HEADERS)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.itemSelectionChanged.connect(self._on_select)

    def load_report(self, report: ComplianceReport) -> None:
        self.setRowCount(0)
        for item in report.items:
            row = self.rowCount()
            self.insertRow(row)
            fg, bg = _COL.get(item.status, ("#ffffff", "#000000"))
            cells = [
                f"{_status_icon(item.status)}  {item.status}",
                item.rule_name,
                item.current_value,
                item.limit_value,
                item.rule_section,
            ]
            for col, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                cell.setData(Qt.UserRole, item)
                cell.setForeground(QColor(fg))
                cell.setBackground(QColor(bg))
                if col == 0:
                    font = QFont()
                    font.setBold(True)
                    cell.setFont(font)
                self.setItem(row, col, cell)
        self.resizeRowsToContents()

    def _on_select(self) -> None:
        rows = self.selectedItems()
        if rows:
            item = rows[0].data(Qt.UserRole)
            if item:
                self.item_selected.emit(item)


# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------

class _DetailPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._title = QLabel("Select a row to see details")
        self._title.setStyleSheet("font-size:14px; font-weight:bold; color:#e94560;")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#333366;")
        layout.addWidget(sep)

        self._msg = QTextEdit()
        self._msg.setReadOnly(True)
        self._msg.setStyleSheet("font-size:13px; line-height:1.5;")
        layout.addWidget(self._msg, 1)

        action_box = QGroupBox("What to do")
        action_layout = QVBoxLayout(action_box)
        self._action = QLabel("")
        self._action.setWordWrap(True)
        self._action.setStyleSheet("font-size:13px; color:#00cc88;")
        action_layout.addWidget(self._action)
        layout.addWidget(action_box)

    def show_item(self, item: ComplianceItem) -> None:
        fg, _ = _COL.get(item.status, ("#ffffff", "#000000"))
        self._title.setText(
            f"{_status_icon(item.status)}  {item.rule_name}  "
            f"<span style='font-size:11px;color:#888;'>({item.rule_section})</span>"
        )
        self._title.setStyleSheet(f"font-size:14px; font-weight:bold; color:{fg};")
        self._msg.setHtml(
            f"<p style='color:#e0e0e0;font-size:13px;'>{item.message}</p>"
            f"<p style='color:#888;font-size:11px;margin-top:8px;'>"
            f"Your value: <b style='color:#fff;'>{item.current_value}</b> &nbsp;|&nbsp; "
            f"Rule limit: <b style='color:#fff;'>{item.limit_value}</b></p>"
        )
        self._action.setText(item.actionable)


# ---------------------------------------------------------------------------
# Rules reference panel
# ---------------------------------------------------------------------------

class _RulesReferencePanel(QWidget):
    """Static display of all rules with source references."""

    _RULES_HTML = """
<style>
  body { background:#0d1b2a; color:#e0e0e0; font-family:sans-serif; font-size:13px; }
  h2   { color:#e94560; border-bottom:1px solid #333366; padding-bottom:4px; }
  h3   { color:#aaaaee; margin-top:16px; }
  table { border-collapse:collapse; width:100%; margin-bottom:12px; }
  th   { background:#0f3460; color:#aaaaee; padding:6px 10px; text-align:left; }
  td   { padding:5px 10px; border-bottom:1px solid #1a2a3a; }
  .ok  { color:#00cc66; }
  .warn{ color:#FFD700; }
  .bad { color:#ff4444; }
  .note{ background:#001133; color:#88aaff; padding:8px; border-radius:4px;
         border-left:3px solid #4466ff; margin:8px 0; }
</style>

<h2>Purdue EV Grand Prix 2025-26 — Rule Reference</h2>

<div class='note'>
  <b>⚠ Important:</b> Items marked ⚠ VERIFY are estimated or partially confirmed.
  Always cross-check every value against the official PDF before race day.<br>
  Official rulebook:
  <i>engineering.purdue.edu/evGrandPrix/highschool/Documents/evGrandPrix-High-School-2025-26-Rules.pdf</i>
</div>

<h3>🔋 Battery — LiTime 48V 60 Ah LiFePO4 (MANDATORY)</h3>
<table>
  <tr><th>Parameter</th><th>Value</th><th>Source</th></tr>
  <tr><td>Chemistry</td><td>LiFePO4 (Lithium Iron Phosphate)</td><td>EVGP Rules</td></tr>
  <tr><td>Nominal voltage</td><td><b>51.2 V</b> (16 cells × 3.2 V)</td><td>EVGP Rules</td></tr>
  <tr><td>Max charge voltage</td><td><b>58.4 V</b> (16 cells × 3.65 V)</td><td>Cell spec</td></tr>
  <tr><td>Min discharge voltage</td><td><b>40.0 V</b> (16 cells × 2.5 V)</td><td>Cell spec</td></tr>
  <tr><td>Capacity</td><td><b>60 Ah  /  3072 Wh</b></td><td>EVGP Rules</td></tr>
  <tr><td>BMS continuous current</td><td><b>120 A</b></td><td>LiTime spec</td></tr>
  <tr><td>Charger voltage</td><td>Must match 51.2 V pack</td><td>EVGP Rules</td></tr>
</table>

<h3>⚡ Controller (MANDATORY MODELS ONLY)</h3>
<table>
  <tr><th>Parameter</th><th>Value</th><th>Source</th></tr>
  <tr><td>Allowed models</td><td><b>Alltrax SPM or SR — 48300, 48400, 48500, 48600</b></td><td>EVGP Rules</td></tr>
  <tr><td><b class='bad'>Max motor current limit</b></td><td><b class='bad'>≤ 220 A</b></td><td>EVGP Rules</td></tr>
  <tr><td><b class='bad'>Max battery current limit</b></td><td><b class='bad'>≤ 220 A</b></td><td>EVGP Rules</td></tr>
  <tr><td>Hi-voltage cutoff</td><td>≤ 58.4 V (battery max)</td><td>Safety</td></tr>
  <tr><td>Lo-voltage cutoff</td><td>≥ 40.0 V (battery min)</td><td>Safety</td></tr>
</table>

<h3>🏎 Chassis</h3>
<table>
  <tr><th>Parameter</th><th>Value</th></tr>
  <tr><td>Allowed chassis</td><td><b>Top-Kart (mandated model)</b></td></tr>
  <tr><td>Modifications</td><td>⚠ VERIFY — check rulebook for allowed mods</td></tr>
</table>

<h3>🔵 Tyres (MANDATORY — no substitutions)</h3>
<table>
  <tr><th>Position</th><th>Compound</th><th>Size</th></tr>
  <tr><td>Front (both)</td><td><b>Hoosier R60B</b></td><td>4.5/10.0/5</td></tr>
  <tr><td>Rear (both)</td><td><b>Hoosier R60B</b></td><td>7.1/11.0/5</td></tr>
</table>

<h3>⚖ Weight ⚠ VERIFY</h3>
<table>
  <tr><th>Parameter</th><th>Value</th></tr>
  <tr><td>Min combined (kart + driver)</td><td>≈ 400 lb / 181 kg — <b>⚠ VERIFY in rulebook</b></td></tr>
  <tr><td>Ballast</td><td>Allowed to reach minimum — must be securely mounted</td></tr>
</table>

<h3>🛡 Safety Requirements ⚠ VERIFY</h3>
<table>
  <tr><th>Item</th><th>Requirement</th></tr>
  <tr><td>Helmet</td><td>Closed-face with integral, immovable chin guard</td></tr>
  <tr><td>Kill switch</td><td>External, accessible by marshals, clearly labelled</td></tr>
  <tr><td>BMS</td><td>Active BMS required — over/under voltage + overcurrent protection</td></tr>
  <tr><td>Main fuse</td><td>Required between battery and controller</td></tr>
  <tr><td>Wiring</td><td>All connections insulated, no exposed conductors</td></tr>
</table>

<h3>👥 Driver / Team Eligibility</h3>
<table>
  <tr><th>Rule</th><th>Limit</th></tr>
  <tr><td>Driver grade</td><td>Grades 9–12 only</td></tr>
  <tr><td>Max karts per school</td><td>4 entries</td></tr>
  <tr><td>Multi-school teams</td><td>Allowed — one school designated lead</td></tr>
</table>

<div class='note'>
  <b>💡 Pro tip:</b> Print this page and bring it to tech inspection.
  Scrutineers will check the same items listed here.
</div>
"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(self._RULES_HTML)
        layout.addWidget(text)


# ---------------------------------------------------------------------------
# Main Rules Tab
# ---------------------------------------------------------------------------

class RulesTab(QWidget):
    """
    Three sub-tabs:
      1. Compliance Check — live check of current settings vs rules
      2. Rule Reference   — human-readable reference of all rules
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._settings = None
        self._gear = None
        self._rules = get_rules()
        self._kart_mass_kg = 90.0
        self._driver_mass_kg = 68.0
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        hdr = QLabel("🏁  Competition Rules & Compliance — Purdue EV Grand Prix 2025-26")
        hdr.setStyleSheet("font-size:16px; font-weight:bold; color:#e94560; padding:6px;")
        layout.addWidget(hdr)

        sub_tabs = QTabWidget()
        layout.addWidget(sub_tabs)

        # ---- Sub-tab 1: Compliance check -----------------------------------
        compliance_widget = self._build_compliance_tab()
        sub_tabs.addTab(compliance_widget, "✅  Compliance Check")

        # ---- Sub-tab 2: Rule reference ------------------------------------
        ref_widget = _RulesReferencePanel()
        sub_tabs.addTab(ref_widget, "📋  Rule Reference")

    def _build_compliance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Top bar: summary + buttons
        top = QHBoxLayout()

        self._summary_label = QLabel("Load a session and open Settings to run compliance check.")
        self._summary_label.setStyleSheet(
            "font-size:13px; font-weight:bold; padding:6px 10px; "
            "background:#0d1b2a; border-radius:4px;"
        )
        top.addWidget(self._summary_label, 1)

        self._run_btn = QPushButton("▶  Run Check")
        self._run_btn.setStyleSheet(
            "background:#0f3460; color:#e0e0e0; font-weight:bold; "
            "padding:6px 18px; border-radius:4px;"
        )
        self._run_btn.clicked.connect(self._run_check)
        top.addWidget(self._run_btn)

        self._edit_btn = QPushButton("✏  Edit Limits")
        self._edit_btn.clicked.connect(self._edit_limits)
        top.addWidget(self._edit_btn)

        layout.addLayout(top)

        # Weight inputs (needed for weight check)
        weight_box = QGroupBox("Weight Inputs (for combined-weight check)")
        weight_form = QHBoxLayout(weight_box)
        weight_form.addWidget(QLabel("Kart mass:"))
        self._kart_spin = QDoubleSpinBox()
        self._kart_spin.setRange(50, 300)
        self._kart_spin.setValue(self._kart_mass_kg)
        self._kart_spin.setSuffix(" kg")
        self._kart_spin.setDecimals(1)
        weight_form.addWidget(self._kart_spin)
        weight_form.addWidget(QLabel("  Driver mass:"))
        self._driver_spin = QDoubleSpinBox()
        self._driver_spin.setRange(30, 200)
        self._driver_spin.setValue(self._driver_mass_kg)
        self._driver_spin.setSuffix(" kg")
        self._driver_spin.setDecimals(1)
        weight_form.addWidget(self._driver_spin)
        combined_note = QLabel(
            f"  → Combined: {self._kart_mass_kg+self._driver_mass_kg:.0f} kg  "
            f"({(self._kart_mass_kg+self._driver_mass_kg)*2.205:.0f} lb)"
        )
        combined_note.setStyleSheet("color:#aaaacc;")
        self._combined_note = combined_note
        weight_form.addWidget(combined_note)
        weight_form.addStretch()
        self._kart_spin.valueChanged.connect(self._update_combined)
        self._driver_spin.valueChanged.connect(self._update_combined)
        layout.addWidget(weight_box)

        # Splitter: table | detail
        splitter = QSplitter(Qt.Horizontal)

        self._table = _ComplianceTable()
        splitter.addWidget(self._table)

        self._detail = _DetailPanel()
        splitter.addWidget(self._detail)

        splitter.setSizes([700, 400])
        layout.addWidget(splitter, 1)

        self._table.item_selected.connect(self._detail.show_item)

        return widget

    def _update_combined(self) -> None:
        k = self._kart_spin.value()
        d = self._driver_spin.value()
        self._combined_note.setText(
            f"  → Combined: {k+d:.0f} kg  ({(k+d)*2.205:.0f} lb)"
        )

    def _run_check(self) -> None:
        if self._settings is None or self._gear is None:
            self._summary_label.setText(
                "⚠  No settings loaded yet — open the Settings tab and configure your controller first."
            )
            self._summary_label.setStyleSheet(
                "font-size:13px; font-weight:bold; padding:6px 10px; "
                "background:#332200; color:#FFD700; border-radius:4px;"
            )
            return

        checker = ComplianceChecker(self._rules)
        report = checker.check(
            self._settings,
            self._gear,
            kart_mass_kg=self._kart_spin.value(),
            driver_mass_kg=self._driver_spin.value(),
        )
        self._table.load_report(report)

        summary = report.summary_line()
        if report.fail_count:
            colour = "#330000"; text_colour = "#ff4444"
        elif report.warn_count:
            colour = "#332200"; text_colour = "#FFD700"
        else:
            colour = "#003311"; text_colour = "#00cc66"

        self._summary_label.setText(summary)
        self._summary_label.setStyleSheet(
            f"font-size:13px; font-weight:bold; padding:6px 10px; "
            f"background:{colour}; color:{text_colour}; border-radius:4px;"
        )

        if self._table.rowCount() > 0:
            self._table.selectRow(0)

    def _edit_limits(self) -> None:
        dlg = _EditLimitsDialog(self._rules, self)
        if dlg.exec_() == QDialog.Accepted:
            updated = dlg.get_updated_rules()
            set_rules(updated)
            self._rules = updated
            if self._settings is not None:
                self._run_check()

    # ------------------------------------------------------------------
    # Public interface called by MainWindow
    # ------------------------------------------------------------------

    def on_settings_changed(self, settings: "AlltraxSettings", gear: "GearRatioConfig") -> None:
        self._settings = settings
        self._gear = gear
        self._run_check()
