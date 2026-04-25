# Strat-OS — Complete Usage Guide

Step-by-step instructions for every feature. Start at the top if this is your first time.

---

## Getting Started

### Step 1 — Install and run (laptop)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

Backend is now at `http://localhost:8000`.

Optional — start the frontend dev server in a second terminal:
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Step 2 — First boot wizard

The first time you open the app you'll see the **First Boot Wizard**. Complete all 6 steps:

1. **Welcome** — read the overview, click Get Started
2. **Admin Account** — create your login (username + password). This is the admin account. Write the password down — there is no recovery.
3. **First Driver** — enter the driver's name. You can skip and add drivers later.
4. **Kart Configuration** — enter the kart name. Note the 220A cap shown on screen.
5. **Storage** — overview of archive options. Configure properly in Settings later.
6. **Done** — click Go to Dashboard.

---

## Creating the Required Entities

Before uploading any data you need at least one of each: **Driver**, **Kart**, and **Track**. The upload form blocks if any are missing.

### Adding a Driver

1. Go to **Drivers** in the sidebar
2. Fill in Name (required) and Notes (optional)
3. Click **Add Driver**

The driver's ML style label appears here once they have enough laps.

### Adding a Kart

1. Go to **Karts** in the sidebar
2. Enter:
   - **Name** — e.g. "Kart #7"
   - **Motor Type** — DC Series (most common for EVGP)
   - **Battery Type** — LiFePO4
   - **Kart Mass (kg)** — kart weight without driver (typically 110–125 kg)
3. Click **Add Kart**

> The 220A max current limit is enforced everywhere. You cannot set it higher.

### Adding a Track

1. Go to **Tracks** in the sidebar
2. Enter the track name
3. Click **Add Track**

The track map is populated automatically when you upload a session with GPS data. You don't need to enter coordinates manually.

---

## Uploading a Session

1. Go to **Upload** (sidebar or Dashboard button)
2. Select:
   - **Driver** — who is driving
   - **Kart** — which kart
   - **Track** — which track
   - **Session Type** — Practice 1/2, Qualifying, Race, or Test
3. Click the file area and pick your **AiM CSV file**
4. Click **Upload & Analyse**

A progress bar appears. The backend will:
- Parse the CSV and create lap records
- Run full telemetry analysis (sectors, corners, energy, smoothness)
- Reconstruct the GPS track map if the CSV has GPS columns
- Extract ML features for the driver
- Update benchmark times

When it finishes you're taken to the Sessions list. Click the session to view results.

> **Tip:** If the upload fails immediately with "All fields required", check that driver, kart, and track are all selected.

---

## Viewing Session Results

Click any session in the Sessions list.

### Lap table

Shows all laps with times and validity flags. ★ marks the best valid lap.

- **Valid** = lap time within 3× the session median (outliers excluded)
- **Invalid** = out-laps, in-laps, laps with sensor dropouts

### Compliance summary

Below the lap table. Shows pass/fail/verify for each EVGP rule applicable to this kart. See [Compliance](#compliance) for detail.

### Recommendations

Plain-English suggestions based on the lap data. Typical examples:
- "Consider raising gear ratio slightly — you're not reaching peak RPM in long straights"
- "Tyre warm-up time is longer than ideal — check pressures"

### Export

Click **Export** to queue a report generation job. When complete, a ZIP file downloads containing:
- `charts/speed_trace_best.png` — speed vs time of the best lap, coloured by phase
- `charts/lap_times.png` — bar chart of all lap times
- `charts/track_map.png` — track outline (if GPS available)
- `report.json` — machine-readable full session data
- `report.txt` — printable pit-wall report (80 columns wide)

---

## Lap Analysis

Click **View →** on any lap row in a session.

### Speed trace

Speed in km/h vs time in seconds. In Engineer mode, the line is coloured by phase:
- Green = accelerating
- Red = braking
- Gold = cornering
- Blue = straight

### Sector splits

The lap is divided into 5 equal-distance sectors. Each card shows:
- Sector time in seconds
- Hover to see distance range and average speed

### Corner analysis (Engineer mode)

Table of every detected corner showing entry/apex/exit speeds in km/h. Use this to identify where the driver is losing or gaining time.

- **Entry speed** = speed 0.5s before apex
- **Apex speed** = minimum speed in the corner
- **Exit speed** = speed 0.5s after apex

High exit speed relative to other laps = better traction / earlier throttle.

### Energy estimate (Engineer mode)

Estimated kWh consumed for that lap based on the speed profile and vehicle mass. Use the delta between laps of the same session to estimate how setup changes affect energy consumption.

---

## Simulation

Go to **Simulation** in the sidebar (Engineer mode only).

### Setting up a simulation

1. Select the session and reference lap — this is the real lap data the simulation will modify
2. Choose the mode:
   - **Mode A** — instant result, changes applied to the recorded speed profile
   - **Mode C** — physics simulation, 2-5 seconds, creates a background job

### Mode A parameters

| Parameter | What it changes | Typical range |
|-----------|----------------|---------------|
| Max Current | Controller current limit | 100–220A (hard cap) |
| Accel Rate × | Multiplier on accelerating phase duration | 0.8–1.3 |
| Speed Limit % | Cap on maximum speed | 80–100% |
| Gear Ratio (new) | Drive ratio vs current setup | ±15% from current |

**Reading the delta chart:**
- X axis = sample index (time progresses left to right)
- Y axis = cumulative time delta in seconds
- Going down = gaining time, going up = losing time
- Where the line slopes down most steeply = where the change is helping most

### Mode C parameters

| Parameter | Effect |
|-----------|--------|
| Goal | Optimise for lap time, energy, or balanced |
| Weight Speed / Energy | How to balance when goal = balanced (0.0–1.0, must sum to 1) |
| Max Current | Controller limit (capped at 220A) |

Mode C uses actual motor physics (torque curve, rolling resistance, aero drag) to predict how the hardware changes would affect the trajectory. It replays the driver's recorded phase sequence (accelerating/braking/cornering) so the simulation assumes the same line and braking points.

### Interpreting results

- **Delta negative** = faster. A delta of −0.5s means the change saves half a second per lap.
- **Predicted time** = estimated lap time with the new settings
- **Energy delta negative** = uses less energy (good for race endurance, not just qualifying pace)

> Mode A is less accurate but instant — use it for quick "what if" questions. Mode C takes longer but accounts for actual motor physics — use it when making real setup decisions.

---

## Track Map

Go to **Tracks** in the sidebar.

Click any track in the list to see its GPS map on the right side. The map is reconstructed automatically from GPS data in uploaded sessions — you don't draw it manually.

### Rebuilding the map

If you've uploaded sessions for this track but the map looks wrong or missing:
1. Click **Rebuild** next to the track name
2. A job queues to re-run GPS reconstruction using the best GPS lap available
3. Wait ~30 seconds and refresh

### Map quality tips

- More laps = better averaging = cleaner map
- The system uses Gaussian smoothing (σ=15 samples) to remove GPS jitter
- If your GPS module has high noise, upload multiple laps so the algorithm can average them

---

## Compliance

Go to **Compliance** in the sidebar, or scroll down on any Session page.

### Reading the compliance table

Each row shows:
- **Status badge** — PASS (green), FAIL (red), WARN (orange), VERIFY (orange)
- **Rule name** — what is being checked
- **Measured** — what the system found (e.g. "200 A")
- **Limit** — what the rule requires (e.g. "≤ 220 A")
- **Message** — plain-English explanation
- **Action** — what to do (shown in blue if action needed)

### VERIFY items

VERIFY means Strat-OS cannot automatically determine compliance — a human must check:
- **Controller model** — must be Alltrax SPM or SR 48300/400/500/600
- **Tyre compound** — must be Hoosier R60B
- **Safety equipment** — helmet, gloves, suit, fire extinguisher

These will always show VERIFY unless you have the Alltrax controller connected and the Alltrax import running.

### Updating rules

Go to **Settings** → Competition Rules section. Enter new values and click Save Rules. Changes apply immediately.

> The 220A maximum current field cannot be set above 220 — this is a hard rule enforced in software.

---

## Driver Styles (ML)

The **Drivers** page shows each driver's detected style once they have enough laps.

### Styles explained

| Style | What it means | What it looks like on track |
|-------|---------------|---------------------------|
| **Aggressive** | High braking intensity, high throttle variance | Late braking, sharp throttle application |
| **Smooth** | High smoothness, high consistency | Progressive braking, gentle throttle, consistent corner exits |
| **Balanced** | Middle of all metrics | Moderate in everything |
| **Inconsistent** | High variance across all metrics | Different technique each lap, hard to predict |

### Confidence score

The percentage shown next to the style label indicates how strongly the ML model assigned that label. < 60% = the driver is borderline between two styles.

### Building the model

- Needs **≥ 5 laps** to train at all (shows nothing below this)
- Bootstrap clustering runs with 5–19 laps
- Incremental classifier runs with 20+ laps
- Training runs automatically after every upload — nothing to configure

### Manually triggering training

```
POST /api/ml/train
Authorization: Bearer <token>
```

Via the API docs at `/docs`. This is rarely needed since training runs automatically.

---

## Storage Management

Go to **Storage** in the sidebar (Engineer mode).

### The storage bar

Shows current SD card usage. The bar changes colour:
- Blue = under 70% (OK)
- Gold = 70–80% (warning)
- Orange = 80–90% (archiving)
- Red = 90%+ (emergency)

### Running cleanup manually

Click **Run Auto-Cleanup**. This:
1. Checks current disk usage
2. If > 80%: moves old raw CSV files to the archive backend
3. If > 90%: additionally deletes archived CSVs (keeps all SQLite data)

You will not lose any lap times, telemetry, or analysis data. Only the original raw CSV files are affected.

### Configuring archive storage

Edit the systemd service environment (on Pi):
```bash
sudo systemctl edit strat-os
```

Add:
```ini
[Service]
Environment=STRATOS_ARCHIVE_BACKEND=smb
Environment=STRATOS_SMB_SHARE=//192.168.73.50/kartarchive
```

Or for Google Drive:
```ini
[Service]
Environment=STRATOS_ARCHIVE_BACKEND=rclone_gdrive
Environment=STRATOS_RCLONE_REMOTE=gdrive:strat-os-archive
```

Then reload: `sudo systemctl daemon-reload && sudo systemctl restart strat-os`

---

## User Management

Go to **Users** in the sidebar (Admin only).

### Creating a new user

1. Enter username (login name, no spaces)
2. Enter display name (shown in the app)
3. Enter password
4. Select role: Admin / Engineer / Viewer
5. Click **Create User**

Share the username and password with the team member. They can change their own password via the API if needed.

### Roles

| Role | Can upload sessions | Can edit karts/drivers | Can manage users | Can edit rules |
|------|--------------------|-----------------------|-----------------|---------------|
| Admin | Yes | Yes | Yes | Yes |
| Engineer | Yes | Yes | No | No |
| Viewer | No | No | No | No |

### Deleting users

Click Delete next to any user (except your own account). Their authentication tokens are immediately invalidated — they'll be logged out on their next request.

---

## Settings

Go to **Settings** in the sidebar.

### System info

Shows the current git commit SHA deployed on this Pi. Use this to verify an auto-update ran correctly.

### Competition rules

Editable rule values for compliance checking. See the [Compliance](#compliance) section for what each field means.

### Archive backend

Instructions for configuring SMB or Google Drive are shown here. Configuration is done via environment variables — see [Storage Management](#storage-management) above.

---

## Running Tests (Before Pi Deployment)

```bash
# Activate venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows

# Run the full test suite
bash scripts/run_tests.sh
```

This runs:
1. **pytest** — unit and integration tests for all backend systems
2. **tsc --noEmit** — TypeScript type check of the entire frontend
3. **smoke_test.py** — starts a real server, uploads a CSV, checks key API responses

All three must pass before deploying to the Pi. The test output will tell you exactly what failed and why.

### Running individual tests

```bash
# All backend tests with verbose output
pytest backend/tests/ -v

# Just one test file
pytest backend/tests/test_compliance.py -v

# Just one test function
pytest backend/tests/test_simulation.py::test_mode_a_220a_hard_cap -v

# End-to-end smoke test
python scripts/smoke_test.py
```

---

## Deploying to Raspberry Pi

### Fresh Pi setup

```bash
# On the Pi, as root:
git clone <your-repo> /home/pi/strat-os
cd /home/pi/strat-os
sudo bash scripts/setup.sh
```

This takes about 5–10 minutes. When complete:
- Wi-Fi hotspot `Strat-OS` is broadcasting (password: `stratosracing`)
- The web app is at `http://strat-os.local` or `http://192.168.73.1:8000`

### Connecting at the track

1. Connect your phone/tablet/laptop to the `Strat-OS` Wi-Fi network
2. Open `http://strat-os.local` in the browser
3. Log in with your credentials

Multiple devices can connect simultaneously. All see the same live data.

### Checking the Pi is healthy

```bash
# SSH to the Pi (from the same network)
ssh pi@strat-os.local

# Check service is running
systemctl status strat-os

# Check for errors
journalctl -u strat-os -n 50

# Check storage
df -h /home/pi/strat-os/data
```

### Updating manually

```bash
ssh pi@strat-os.local
cd /home/pi/strat-os
git pull
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build && cd ..
sudo systemctl restart strat-os
```

Auto-update does all of this automatically at boot when there's internet.

---

## Troubleshooting Quick Reference

| Problem | First check | Fix |
|---------|------------|-----|
| Can't log in | Check username/password | Reset: SSH to Pi, delete auth_tokens table row |
| Upload fails with 422 | All 3 entity IDs selected? | Select driver + kart + track before uploading |
| No laps after upload | Check job status | `GET /api/jobs/{id}` — read error_msg |
| Track map not showing | GPS in CSV? | Check the CSV has Latitude/Longitude columns |
| Compliance shows wrong current | Kart settings not set | Edit kart → set Alltrax settings |
| Simulation error | Lap has telemetry? | `GET /api/laps/{id}/telemetry` — check arrays are populated |
| ML style not showing | Enough laps? | Driver needs ≥ 5 laps with feature vectors |
| Storage bar is red | > 90% full | Run cleanup from Storage page, or configure archive backend |
| Pi not reachable | Connected to Strat-OS Wi-Fi? | Check Wi-Fi, try IP directly: `192.168.73.1:8000` |
| Auto-update not running | Has internet at boot? | `cat /var/log/strat-os-update.log` |
