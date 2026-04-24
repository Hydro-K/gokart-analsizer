"""
Help & Guide Tab — EV Kart Data Analyzer.

Covers:
  • Getting started / exporting from AiM Race Studio 3
  • How to read every chart in the app
  • How to interpret recommendations
  • How to run simulations
  • Alltrax controller quick-reference
  • Glossary of terms
"""

from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QTabWidget, QListWidget, QListWidgetItem, QSplitter,
)
from PyQt5.QtCore import Qt


# ---------------------------------------------------------------------------
# Help content (HTML strings, one per section)
# ---------------------------------------------------------------------------

_CSS = """
<style>
body { background:#0d1b2a; color:#e0e0e0; font-family:'Segoe UI',sans-serif;
       font-size:13px; line-height:1.65; margin:12px; }
h1   { color:#e94560; font-size:20px; border-bottom:2px solid #333366;
       padding-bottom:6px; margin-top:4px; }
h2   { color:#aaaaee; font-size:15px; margin-top:20px; border-left:3px solid #e94560;
       padding-left:8px; }
h3   { color:#88aaff; font-size:13px; margin-top:14px; }
b    { color:#ffffff; }
code { background:#1a2a3a; color:#00BFFF; padding:1px 5px;
       border-radius:3px; font-family:monospace; }
.tip  { background:#001133; border-left:4px solid #00BFFF; padding:8px 12px;
        border-radius:0 4px 4px 0; margin:8px 0; }
.warn { background:#332200; border-left:4px solid #FFD700; padding:8px 12px;
        border-radius:0 4px 4px 0; margin:8px 0; }
.good { background:#003311; border-left:4px solid #00cc66; padding:8px 12px;
        border-radius:0 4px 4px 0; margin:8px 0; }
ul   { margin:4px 0; padding-left:20px; }
li   { margin:3px 0; }
table{ border-collapse:collapse; width:100%; margin:8px 0; }
th   { background:#0f3460; color:#aaaaee; padding:6px 10px; text-align:left; }
td   { padding:5px 10px; border-bottom:1px solid #1a2a3a; }
</style>
"""

_SECTIONS = {

"🚀  Getting Started": _CSS + """
<h1>Getting Started</h1>

<h2>Step 1 — Export data from AiM Race Studio 3</h2>
<ol>
  <li>Connect the AiM Solo 2 logger via USB and open Race Studio 3.</li>
  <li>Select your session in the left panel.</li>
  <li>Click <b>File → Export → CSV</b>.</li>
  <li>Make sure <b>"GPS Speed"</b>, <b>"GPS Lat"</b>, <b>"GPS Lon"</b>, and <b>"GPS Beacon"</b>
      channels are ticked.</li>
  <li>Export — the file will be a <code>.csv</code> with a metadata header, a units row,
      then numeric data.</li>
</ol>

<div class='tip'>
  <b>💡 Multiple sessions:</b> You can export every session from one device and load them
  all at once using the Session tab's <b>"Load Multiple Files"</b> button.
  Great for comparing practice vs. qualifying vs. race.
</div>

<h2>Step 2 — Load data into the analyzer</h2>
<ol>
  <li>Open the <b>Session</b> tab.</li>
  <li>Click <b>Browse CSV</b> under Driver 1.</li>
  <li>Enter the driver's name in the text box.</li>
  <li>Click <b>Load Session</b>.</li>
  <li>Optionally load a second driver under Driver 2 for direct comparison.</li>
</ol>

<div class='warn'>
  <b>⚠ SCCA / multiple files:</b> To compare multiple AiM CSV files from the same device,
  use the <b>"Load Multiple Files"</b> button in the Session tab — this creates a
  session list and lets you pick any two for comparison.
</div>

<h2>Step 3 — Import Alltrax settings</h2>
<ol>
  <li>In Alltrax Toolkit, connect to the controller and click <b>Save Settings</b>
      (saves a <code>.aep</code> or <code>.txt</code> file).</li>
  <li>In this app, open the <b>Settings</b> tab → <b>"Import from Alltrax Toolkit…"</b>.</li>
  <li>The app will read every parameter and populate the sliders automatically.</li>
</ol>

<h2>Step 4 — Run compliance check</h2>
<p>Open the <b>Rules</b> tab and click <b>Run Check</b>.
Any setting that violates the EVGP rules turns <span style='color:#ff4444;'>red</span> immediately.</p>

<h2>Step 5 — Read the recommendations</h2>
<p>The <b>Recommendations</b> tab lists specific parameter changes ranked by impact.
Every suggestion is verified against EVGP limits before it is shown —
you will never be told to set the current above 220 A.</p>

<h2>Step 6 — Run a simulation</h2>
<p>Open the <b>Simulation</b> tab, adjust gear ratio / current / tyre PSI sliders,
and watch the projected speed trace and lap time update in real time.</p>
""",

"📈  Reading the Speed Trace": _CSS + """
<h1>Reading the Speed Trace</h1>

<h2>What is a speed trace?</h2>
<p>A speed trace is a graph of the kart's speed over time during one lap.
It is the most important chart in motorsport data analysis.</p>

<h2>How to read it</h2>
<table>
  <tr><th>What you see</th><th>What it means</th></tr>
  <tr><td><b>Rising slope</b> (speed going up)</td>
      <td>Kart is <b>accelerating</b> — motor is applying power.</td></tr>
  <tr><td><b>Falling slope</b> (speed going down)</td>
      <td>Kart is <b>braking</b> — driver is on the brakes.</td></tr>
  <tr><td><b>V-shaped dip</b></td>
      <td>A <b>corner</b> — speed drops into the apex, then rises on exit.</td></tr>
  <tr><td><b>Flat top</b></td>
      <td>Speed-limited straight — the kart has hit its top speed.</td></tr>
  <tr><td><b>Coloured overlay</b></td>
      <td>Phase labels: <span style='color:#00cc66;'>green=accelerating</span>,
          <span style='color:#ff4444;'>red=braking</span>,
          <span style='color:#FFD700;'>yellow=cornering</span>,
          <span style='color:#00BFFF;'>blue=straight</span>.</td></tr>
</table>

<h2>What to look for</h2>
<ul>
  <li><b>Inconsistent V-shapes:</b> Each corner dip should look the same lap-to-lap.
      Variation means inconsistent braking or turn-in points.</li>
  <li><b>Slow exit speed:</b> If speed is still low 2–3 seconds after a corner apex,
      the driver is exiting too slowly or the current limit is too low.</li>
  <li><b>Flat acceleration ramp:</b> A gradual rise after a corner usually means
      the accel_rate is set too low — the controller is ramping up slowly.</li>
  <li><b>Plateau before the next corner:</b> Good — the kart reached full speed
      on the straight. If there is no plateau, the gear ratio may be too tall
      (not enough torque to spin up before the next corner).</li>
</ul>

<div class='tip'>
  <b>💡 Projection line:</b> The dotted line on the speed trace is the <em>projected</em>
  speed with your new settings. If the dotted line is above the solid line on corner exits,
  your changes will make the kart faster there.
</div>

<h2>Comparing two drivers</h2>
<p>On the Comparison tab both speed traces are overlaid.
The <b>delta plot</b> below shows time gained/lost — if the line goes down,
Driver 1 is losing time to Driver 2 at that moment.</p>
""",

"🔵  Track Map": _CSS + """
<h1>Track Map (GPS)</h1>

<h2>What is it?</h2>
<p>The track map draws the kart's path around the circuit using GPS coordinates,
coloured by speed — <span style='color:#0000ff;'>blue = slow</span>,
<span style='color:#ff0000;'>red = fast</span> (plasma colour scale).</p>

<h2>How to read it</h2>
<ul>
  <li><b>Dark/blue sections</b> — low speed areas (corners, chicanes).</li>
  <li><b>Yellow/red sections</b> — high speed areas (straights).</li>
  <li><b>Compare two laps:</b> Load two sessions and compare maps — differences in
      braking/apex points show up as colour differences at the same physical location.</li>
</ul>

<h2>No GPS? Circular fallback</h2>
<p>If the AiM file has no GPS data, the app draws a circular approximation
based on speed and time.  The shape is not accurate, but corner timing still works.</p>

<div class='tip'>
  <b>💡 Tip:</b> Zoom in on a specific corner using the toolbar (magnifying glass icon)
  to see exactly where minimum speed occurs lap-to-lap.
</div>
""",

"⏱  Lap Times & Sectors": _CSS + """
<h1>Lap Times & Sector Analysis</h1>

<h2>Lap Times table</h2>
<table>
  <tr><th>Column</th><th>Meaning</th></tr>
  <tr><td><b>Lap</b></td><td>Lap number (1 = first complete lap after beacon).</td></tr>
  <tr><td><b>Time</b></td><td>Total lap time in MM:SS.mmm format.</td></tr>
  <tr><td><b>Δ Best</b></td><td>How many seconds slower than the best lap.
      Negative means it IS the best lap.</td></tr>
  <tr><td><b>Max Speed</b></td><td>Highest speed reached during that lap.</td></tr>
  <tr><td><b>Avg Speed</b></td><td>Average speed across the full lap.</td></tr>
</table>

<h2>Sector Analysis</h2>
<p>The lap is split into 5 equal-distance sectors.  For each sector you see:</p>
<ul>
  <li><b>Best sector time</b> — the fastest any lap achieved that sector.</li>
  <li><b>Theoretical best lap</b> — adds up all best sectors.
      This is the <em>perfect lap</em> if you could combine your best driving in every sector.
      The gap between your actual best lap and the theoretical best shows where you have
      the most time left to find.</li>
</ul>

<div class='good'>
  <b>✅ What to aim for:</b> Consistency score > 95%.
  A high consistency means your lap times are clustered — you are repeating your fastest
  driving reliably.  Wild variation usually means tyre temperature swings or driver errors.
</div>
""",

"🔧  Corners & Acceleration": _CSS + """
<h1>Corners & Acceleration Analysis</h1>

<h2>Corner speed chart</h2>
<p>Every detected corner is shown as a box — the box spans the braking zone to the
exit zone.  Inside you see:</p>
<ul>
  <li><b>Apex speed</b> — minimum speed at the tightest point of the corner.</li>
  <li><b>Exit speed</b> — speed 1 second after the apex — most important number.</li>
  <li><b>Box height</b> — spread across laps (tall box = inconsistent corner).</li>
</ul>

<h2>What low corner exit speed means</h2>
<ul>
  <li>Driver braking too late → not settled for apex.</li>
  <li><b>Max current too low</b> → not enough torque to drive out of the corner.</li>
  <li><b>Accel rate too low</b> → motor takes too long to reach full current.</li>
  <li>Rear tyre pressure too high → tyres skidding on exit.</li>
</ul>

<h2>Acceleration chart</h2>
<p>Shows speed vs. time from standstill (or corner exit).
The <b>shaded envelope</b> is the projected range with your new settings.
Look for:</p>
<ul>
  <li><b>S-shaped initial rise</b> — normal with low accel_rate.
      Higher accel_rate makes the initial slope steeper.</li>
  <li><b>Flat top</b> — motor has hit the current limit.
      Raising max current lifts this ceiling.</li>
</ul>

<div class='warn'>
  <b>⚠ EVGP Rule:</b> Max current is capped at <b>220 A</b>.
  The app enforces this — you cannot enter a value above 220 A without a rule violation flag.
</div>
""",

"⚙️  Controller Settings Guide": _CSS + """
<h1>Alltrax Controller Settings — Plain English Guide</h1>

<h2>Max Current (A)</h2>
<p><b>What it does:</b> Sets the highest current the controller will send to the motor.
More current = more torque = faster acceleration.</p>
<p><b>Trade-off:</b> More current = more heat in motor and controller.
High heat causes thermal derating (the controller reduces power automatically to protect itself).</p>
<p><b>EVGP limit: ≤ 220 A.</b> Recommended starting point: 180–200 A for endurance racing.</p>

<h2>Acceleration Rate (1–255)</h2>
<p><b>What it does:</b> Controls how fast the controller ramps up from 0 to max current
when you press the throttle.  Low value = slow ramp (smooth but sluggish).
High value = instant full current (aggressive but can spin wheels).</p>
<p><b>Typical range:</b> 64–160 for kart racing.  Higher for tight tracks, lower for wet.</p>

<h2>Deceleration Rate (1–255)</h2>
<p><b>What it does:</b> Controls plug braking — how hard the motor resists motion
when you release the throttle.  Only relevant if regen braking is ON.</p>

<h2>Speed Limit (%)</h2>
<p><b>What it does:</b> Caps the motor RPM at a percentage of maximum.
At 100% the controller delivers full top speed.
At 70% the kart is limited to 70% of theoretical top speed.</p>
<p><b>Use case:</b> Wet weather, tight tracks, or if your gear ratio exceeds the EVGP
speed limit — lower this instead of changing sprockets.</p>

<h2>Lo-Voltage Cutoff (V)</h2>
<p><b>What it does:</b> The controller cuts power if the battery drops below this voltage.
Protects the LiFePO4 cells from over-discharge, which causes permanent damage.</p>
<p><b>Set to:</b> ≥ 40.0 V for the mandated 16S LiFePO4 pack.</p>

<h2>Hi-Voltage Cutoff (V)</h2>
<p><b>What it does:</b> The controller refuses to operate above this voltage.
Protects cells from over-charge during regeneration.</p>
<p><b>Set to:</b> ≤ 58.4 V for the mandated 16S LiFePO4 pack.</p>

<h2>Throttle Curve</h2>
<p>Maps physical pedal position (0–100%) to controller output (0–100%).
A non-linear curve lets you customise throttle feel:</p>
<table>
  <tr><th>Preset</th><th>Best for</th></tr>
  <tr><td><b>Linear</b></td><td>Consistent, predictable — good for learning drivers.</td></tr>
  <tr><td><b>Aggressive</b></td><td>High output at low pedal — maximum corner exit response.</td></tr>
  <tr><td><b>Soft S-Curve</b></td><td>Gentle initial response — good for wet or slippery conditions.</td></tr>
  <tr><td><b>Late Apex</b></td><td>Delayed initial response, snappy at full pedal — trail-braking style.</td></tr>
</table>

<h2>Regen Braking</h2>
<p>When enabled, releasing the throttle causes the motor to act as a generator,
feeding energy back to the battery and slowing the kart.
Useful on tracks with many long braking zones to extend battery range.</p>
""",

"🏁  Simulation Guide": _CSS + """
<h1>Running Simulations</h1>

<h2>What the simulation does</h2>
<p>The Simulation tab takes your actual recorded lap and mathematically models
what would happen if you changed one parameter at a time.
It predicts a new speed trace and calculates a projected lap time.</p>

<div class='tip'>
  <b>💡 Key idea:</b> The simulation uses real track data (corners, straights, braking zones)
  from your loaded session.  It is not a generic model — it is <em>your</em> track with
  <em>your</em> driver's style, changed only where the parameter would have an effect.
</div>

<h2>Parameters you can simulate</h2>
<table>
  <tr><th>Parameter</th><th>Effect modelled</th></tr>
  <tr><td><b>Max Current</b></td>
      <td>More current → higher torque → faster acceleration out of corners.
          Also models thermal derating above 70 °C motor temp.</td></tr>
  <tr><td><b>Accel Rate</b></td>
      <td>Higher rate → controller reaches full current faster after corner apex.</td></tr>
  <tr><td><b>Gear Ratio</b> (motor/axle sprockets)</td>
      <td>Shorter ratio (fewer axle teeth) → higher top speed, less torque.
          Longer ratio → more torque, lower top speed.
          The simulation shifts the entire speed curve accordingly.</td></tr>
  <tr><td><b>Tyre PSI</b></td>
      <td>Affects rolling resistance and grip.  Optimum is typically 14–18 PSI
          for Hoosier R60B.  Too high → skidding on exit.  Too low → sluggish.</td></tr>
  <tr><td><b>Kart + Driver Mass</b></td>
      <td>Lighter kart accelerates faster and brakes shorter.
          Used to evaluate ballast decisions.</td></tr>
  <tr><td><b>Motor Temperature</b></td>
      <td>Above 70 °C the Alltrax begins thermal derating — peak current is reduced
          automatically.  Setting 90 °C shows how much performance is lost.</td></tr>
</table>

<h2>How to read the simulation chart</h2>
<ul>
  <li><b>Solid line</b> — actual recorded speed (baseline).</li>
  <li><b>Dashed line</b> — projected speed with new settings.</li>
  <li><b>Green fill</b> — sections where new settings are faster.</li>
  <li><b>Red fill</b> — sections where new settings are slower.</li>
  <li><b>Δ Lap Time box</b> — total predicted time saved (negative = faster).</li>
</ul>

<h2>Tip: sweep a parameter</h2>
<p>Move the Max Current slider from 150 A → 220 A while watching the Δ lap time.
The point where the curve flattens is your diminishing-returns point —
adding more current there gives less and less benefit while increasing heat.</p>

<div class='warn'>
  <b>⚠ Remember:</b> Any simulation that would require setting max current > 220 A
  is automatically flagged.  The Rules tab shows the violation in red.
</div>
""",

"📤  Alltrax Import/Export": _CSS + """
<h1>Importing & Exporting Alltrax Settings</h1>

<h2>Importing from Alltrax Toolkit</h2>
<ol>
  <li>Connect your controller to a PC via the Alltrax USB interface.</li>
  <li>Open <b>Alltrax Toolkit</b> and connect to the controller.</li>
  <li>Click <b>File → Save Settings</b> — this creates a <code>.aep</code> file
      (also called a parameter file).</li>
  <li>In this app, open the <b>Settings</b> tab → <b>"Import from Alltrax…"</b>.</li>
  <li>Select the <code>.aep</code> file.  All parameters are loaded automatically.</li>
</ol>

<div class='tip'>
  <b>💡 Tip:</b> The app can also read plain-text exports (key=value format)
  and our own JSON format.  Any of these will populate the sliders correctly.
</div>

<h2>Exporting from this app back to Alltrax Toolkit</h2>
<ol>
  <li>Open <b>Settings</b> tab → adjust parameters as desired.</li>
  <li>Click <b>"Export Alltrax Settings…"</b>.</li>
  <li>Save as JSON or AEP format.</li>
  <li>In Alltrax Toolkit, click <b>File → Load Settings</b> and select the exported file.</li>
  <li>Click <b>Program Controller</b> to write the settings to the hardware.</li>
</ol>

<h2>What parameters are imported</h2>
<table>
  <tr><th>AEP Key</th><th>App parameter</th></tr>
  <tr><td><code>MaxCurrent</code> / <code>max_current</code></td><td>Max Current (A)</td></tr>
  <tr><td><code>AccelRate</code> / <code>accel_rate</code></td><td>Acceleration Rate</td></tr>
  <tr><td><code>DecelRate</code> / <code>decel_rate</code></td><td>Deceleration Rate</td></tr>
  <tr><td><code>SpeedLimit</code> / <code>speed_limit</code></td><td>Speed Limit (%)</td></tr>
  <tr><td><code>LowVoltCutoff</code></td><td>Lo-Voltage Cutoff (V)</td></tr>
  <tr><td><code>HighVoltCutoff</code></td><td>Hi-Voltage Cutoff (V)</td></tr>
  <tr><td><code>ThrottleCurve</code></td><td>Throttle Curve (11 points)</td></tr>
  <tr><td><code>RegenBraking</code></td><td>Regen Braking on/off</td></tr>
</table>
""",

"📖  Glossary": _CSS + """
<h1>Glossary of Terms</h1>

<table>
  <tr><th>Term</th><th>Plain-English meaning</th></tr>
  <tr><td><b>Apex</b></td>
      <td>The geometric centre of a corner — the point where the kart is closest to
          the inside kerb.  Also the point of minimum speed.</td></tr>
  <tr><td><b>Beacon / Lap trigger</b></td>
      <td>An infrared transponder at the start/finish line that tells the logger a
          new lap has started.</td></tr>
  <tr><td><b>BMS</b></td>
      <td>Battery Management System — electronics inside the battery pack that monitor
          voltage and current and disconnect the pack if limits are exceeded.</td></tr>
  <tr><td><b>Consistency %</b></td>
      <td>How similar your lap times are to each other.  100% = identical laps.
          95%+ is considered good for endurance racing.</td></tr>
  <tr><td><b>Derating</b></td>
      <td>When the controller automatically reduces power to protect itself from overheating.
          You feel it as the kart suddenly feeling slower mid-race.</td></tr>
  <tr><td><b>Delta / Δ</b></td>
      <td>The difference between two values.  "Δ lap time −0.3 s" means 0.3 seconds faster.</td></tr>
  <tr><td><b>Gear ratio</b></td>
      <td>Motor sprocket teeth ÷ axle sprocket teeth.  Smaller ratio = higher top speed,
          less torque.  Larger ratio = more torque, lower top speed.</td></tr>
  <tr><td><b>Hz (sample rate)</b></td>
      <td>How many times per second the logger records data.  AiM Solo 2 typically logs at
          10–25 Hz.  Higher Hz gives smoother graphs.</td></tr>
  <tr><td><b>Jerk</b></td>
      <td>The rate of change of acceleration.  High jerk = abrupt inputs.
          Smooth drivers have low jerk (smoother speed trace).</td></tr>
  <tr><td><b>LiFePO4</b></td>
      <td>Lithium Iron Phosphate battery chemistry — mandated for EVGP 2025-26.
          Very safe and long-lasting.  Nominal cell voltage: 3.2 V.</td></tr>
  <tr><td><b>Phase</b></td>
      <td>What the kart is doing at a given moment: accelerating, braking, cornering, or straight.</td></tr>
  <tr><td><b>Plug braking</b></td>
      <td>Slowing the kart by running the motor in reverse (no physical brakes used).
          Controlled by the decel_rate parameter.</td></tr>
  <tr><td><b>Regen braking</b></td>
      <td>Regenerative braking — motor acts as a generator when slowing, feeding energy
          back into the battery.  Extends range on tracks with long braking zones.</td></tr>
  <tr><td><b>Sector</b></td>
      <td>A portion of the track, usually 1/5 of the total distance.
          Sector times help pinpoint where time is won or lost.</td></tr>
  <tr><td><b>Theoretical best lap</b></td>
      <td>The lap time you would achieve if you could combine your best performance
          in every sector from any lap.  Always faster than any actual lap.</td></tr>
  <tr><td><b>Torque</b></td>
      <td>Rotational force — what actually accelerates the kart out of corners.
          Proportional to current in an electric motor.</td></tr>
</table>
""",
}


# ---------------------------------------------------------------------------
# Help Tab widget
# ---------------------------------------------------------------------------

class HelpTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        hdr = QLabel("📖  Help & User Guide — EV Kart Data Analyzer")
        hdr.setStyleSheet("font-size:16px; font-weight:bold; color:#e94560; padding:6px;")
        layout.addWidget(hdr)

        splitter = QSplitter(Qt.Horizontal)

        # Left: section list
        self._list = QListWidget()
        self._list.setMaximumWidth(220)
        self._list.setStyleSheet(
            "QListWidget { background:#0d1b2a; border:1px solid #333366; font-size:13px; }"
            "QListWidget::item { padding:8px 6px; color:#c0c0e0; }"
            "QListWidget::item:selected { background:#0f3460; color:#ffffff; }"
        )
        for title in _SECTIONS:
            item = QListWidgetItem(title)
            self._list.addItem(item)
        splitter.addWidget(self._list)

        # Right: content
        self._content = QTextEdit()
        self._content.setReadOnly(True)
        self._content.setStyleSheet("background:#0d1b2a; border:1px solid #333366;")
        splitter.addWidget(self._content)

        splitter.setSizes([220, 900])
        layout.addWidget(splitter)

        self._list.currentRowChanged.connect(self._show_section)
        self._list.setCurrentRow(0)

    def _show_section(self, row: int) -> None:
        keys = list(_SECTIONS.keys())
        if 0 <= row < len(keys):
            self._content.setHtml(_SECTIONS[keys[row]])
