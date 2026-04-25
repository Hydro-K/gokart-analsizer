# Strat-OS — EV Kart Race Engineering Platform

Strat-OS is a fully offline, Raspberry Pi-hosted web application for EV kart race engineering. Upload AiM CSV telemetry, analyse laps, run simulations, check compliance, and review driver performance — all from any device connected to the kart's Wi-Fi hotspot.

## Documentation

| Document | Description |
|----------|-------------|
| **README.md** (this file) | Installation, quick start, API reference, troubleshooting |
| [docs/HOW_TO_USE.md](docs/HOW_TO_USE.md) | Complete step-by-step usage guide for every feature |
| [docs/SYSTEMS.md](docs/SYSTEMS.md) | How every system works internally — algorithms, data flow, design decisions |

---

## Table of Contents

1. [Quick Start (Laptop / Dev)](#1-quick-start-laptop--dev)
2. [Raspberry Pi Deployment](#2-raspberry-pi-deployment)
3. [First Boot Wizard](#3-first-boot-wizard)
4. [Uploading a Session](#4-uploading-a-session)
5. [Lap Analysis](#5-lap-analysis)
6. [Simulation](#6-simulation)
7. [Compliance](#7-compliance)
8. [Driver Styles (ML)](#8-driver-styles-ml)
9. [Storage Management](#9-storage-management)
10. [User Management](#10-user-management)
11. [Settings & Rules](#11-settings--rules)
12. [Running Tests](#12-running-tests)
13. [Architecture Overview](#13-architecture-overview)
14. [API Reference](#14-api-reference)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Quick Start (Laptop / Dev)

### Prerequisites
- Python 3.11+ (3.14 works)
- Node.js 18+

### Backend

```bash
# From the project root
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r backend/requirements.txt

uvicorn backend.main:app --reload
```

The API will be at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

The UI will be at `http://localhost:5173` (proxies `/api` to port 8000 automatically).

### First run

On a fresh database the first page you see is the **First Boot Wizard**. It guides you through creating an admin account, your first driver, and your first kart. You can also skip those steps and add them later from the sidebar.

---

## 2. Raspberry Pi Deployment

### Prerequisites
- Raspberry Pi 4 (2 GB+ RAM recommended)
- Pi OS Bookworm 64-bit (fresh install)
- Internet connection during setup only

### Steps

```bash
# 1. Clone the repo onto the Pi
git clone <your-repo-url> /home/pi/strat-os
cd /home/pi/strat-os

# 2. Run the setup script (as root)
sudo bash scripts/setup.sh
```

The script will:
- Install Python, Node, SQLite, rclone, cifs-utils, hostapd, dnsmasq
- Create a Python venv and install all dependencies
- Build the React frontend
- Initialise the database
- Install and start a `systemd` service (`strat-os.service`)
- Configure a Wi-Fi hotspot: **SSID `Strat-OS`, password `stratosracing`**

Once complete, connect any device to the `Strat-OS` Wi-Fi network and open:

```
http://strat-os.local
```
or
```
http://192.168.73.1:8000
```

> The Pi has **no screen attached**. All access is via browser over the hotspot.

### Auto-update

Every time the Pi boots and has internet access it checks for updates automatically:

```
strat-os-update.service  →  runs auto_update.sh before strat-os.service
```

`auto_update.sh` pings `8.8.8.8`, fetches the git remote, and if there are new commits it pulls, reinstalls Python deps, rebuilds the frontend, and restarts the service. If there's no internet it skips silently.

---

## 3. First Boot Wizard

Triggered automatically when no users exist in the database.

| Step | What it does |
|------|-------------|
| Welcome | Overview of Strat-OS |
| **Create Admin Account** | Username + password — secured before anything else |
| Add First Driver | Name of the person who drives the kart |
| Configure Kart | Kart name — 220A EVGP cap is shown explicitly |
| Storage | Overview of archive tier options |
| Done | Redirects to Dashboard |

You can skip the driver and kart steps and create them later in the **Drivers** and **Karts** pages.

---

## 4. Uploading a Session

Before uploading you need:
- At least one **Driver** (Sidebar → Drivers → Add)
- At least one **Kart** (Sidebar → Karts → Add)
- At least one **Track** (Sidebar → Tracks → Add)

Then go to **Upload** (or click "Upload Session" on Dashboard):

1. Select the **Driver**
2. Select the **Kart**
3. Select the **Track**
4. Choose a **Session Type** (Practice 1/2, Qualifying, Race, Test)
5. Click the file area and select your **AiM CSV file**
6. Click **Upload & Analyse**

A job progress indicator appears. The backend will:
1. Parse the CSV and detect laps
2. Run full analysis (sectors, corners, energy, smoothness)
3. Reconstruct the GPS track map (if GPS data present)
4. Extract ML features for driver style
5. Auto-trigger ML training if driver has ≥ 5 laps
6. Update benchmark times for that driver/kart/track combination

When the job completes you're taken to the Sessions list.

---

## 5. Lap Analysis

### Session Detail Page

Click any session to see:
- **Lap table** — all laps with times, validity, and a ★ on the best lap
- **Compliance summary** — pass/fail/verify for each EVGP rule
- **Recommendations** — plain-English setup suggestions
- **Export** button — generates a ZIP (charts + JSON + printable TXT report)

### Individual Lap Page

Click "View →" on any lap row:

- **Speed trace** — km/h vs time, coloured by phase (accelerating/braking/cornering/straight) in Engineer mode
- **Sector splits** — time and average speed per sector
- **Corner analysis** — entry/apex/exit speed per corner (Engineer mode)
- **Energy estimate** — estimated kWh consumed

### Beginner vs Engineer Mode

Toggle in the bottom of the sidebar. Beginner mode hides sector heatmaps, raw data arrays, energy charts, corner tables, and Mode C simulation. Everything is still visible in Engineer mode.

---

## 6. Simulation

Go to **Simulation** in the sidebar (Engineer mode only).

### Mode A — Fast Linear (<100ms)

What it tests: how changes to controller current, acceleration rate, speed limit, gear ratio, or mass affect lap time.

1. Select a session and a reference lap
2. Choose **Mode A**
3. Adjust parameters:
   - **Max Current** — capped hard at 220A (EVGP rule)
   - **Accel Rate** — multiplier on acceleration phase (1.0 = unchanged, 1.2 = 20% more)
   - **Speed Limit %** — cap maximum speed (e.g. 90 = limit to 90% of actual max)
   - **Gear Ratio (new)** — compare to current ratio
4. Click **Run Mode A**
5. Results show: delta lap time (negative = faster), predicted time, energy delta, and a time-delta-over-lap chart

### Mode C — Physics ODE (2-5 seconds, async)

More realistic: uses the actual motor torque curve, battery model, and driver phase replay from the reference lap.

1. Select session and lap
2. Choose **Mode C**
3. Set goal (lap time, energy, or balanced), weights, and current
4. Click **Queue Mode C**
5. A job progress bar appears — poll until done
6. Results shown when job completes

> 220A is enforced in three places: the Pydantic schema (rejects > 220 with a 422 error), the Mode A function, and the Mode C ODE. Requesting 250A will silently be capped to 220A.

---

## 7. Compliance

Go to **Compliance** in the sidebar, or click "Compliance" on any Session Detail page.

The checker runs against EVGP rules stored in the database (configurable in Settings):

| Check | Rule |
|-------|------|
| Controller current | ≤ 220A |
| Battery voltage | Within min/max range |
| Speed | ≤ limit km/h |
| Combined weight | ≥ minimum kg |

Status codes:
- **PASS** — within limits
- **FAIL** — out of limits
- **VERIFY** — needs manual inspection (e.g. weight)

The overall session status is PASS only if all items are PASS or VERIFY.

---

## 8. Driver Styles (ML)

Strat-OS automatically classifies each driver's style based on their lap telemetry. No manual labelling is required.

**How it works:**
1. After ingestion, 5 features are extracted per lap: throttle variance, braking intensity, corner entry speed, acceleration consistency, smoothness score
2. Once a driver has ≥ 5 laps, an ML training job is auto-submitted
3. With < 20 laps: MiniBatchKMeans clusters the laps, centroids are mapped to style labels
4. With ≥ 20 laps: SGDClassifier trains incrementally using the cluster labels as seeds
5. The driver's style is the majority-vote label across recent laps (most recent third weighted 2×)

**Styles:**
- **Aggressive** — high braking intensity, high throttle variance, low consistency
- **Smooth** — high smoothness score, high consistency, low throttle variance
- **Balanced** — moderate across all features
- **Inconsistent** — high variance, low smoothness, low consistency

Style and confidence appear on the **Drivers** page next to each driver's name.

To retrain manually: go to any page with the API docs open (`/docs`) and call `POST /api/ml/train`.

---

## 9. Storage Management

Go to **Storage** in the sidebar (Engineer mode).

### Tiers and thresholds

| Usage | Action |
|-------|--------|
| < 70% | OK — no action |
| 70–80% | Warning shown in sidebar |
| 80–90% | **Archive** — raw CSV files moved to archive backend |
| > 90% | **Emergency** — raw CSVs on archive deleted (SQLite rows + telemetry kept) |

### Archive backends

Set via environment variable before starting the service:

```bash
# No archiving (default)
STRATOS_ARCHIVE_BACKEND=disabled

# Copy to an SMB network share (another PC on the hotspot)
STRATOS_ARCHIVE_BACKEND=smb
STRATOS_SMB_SHARE=//192.168.73.50/kartarchive

# Sync to Google Drive via rclone (when internet available)
STRATOS_ARCHIVE_BACKEND=rclone_gdrive
STRATOS_RCLONE_REMOTE=gdrive:strat-os-archive
```

Configure these in `/etc/systemd/system/strat-os.service` on the Pi, then `sudo systemctl daemon-reload && sudo systemctl restart strat-os`.

The Pi always runs independently — archiving is best-effort. If the network peer is unreachable, the job stays pending and retries on the next cleanup cycle.

### Manual cleanup

Click **Run Auto-Cleanup** on the Storage page to trigger the cleanup logic immediately.

---

## 10. User Management

Go to **Users** in the sidebar (Admin only).

### Roles

| Role | Capabilities |
|------|-------------|
| **Admin** | Full access: create/delete users, edit rules, all data |
| **Engineer** | Upload sessions, edit drivers/karts/tracks, view everything |
| **Viewer** | Read-only access to all data |

### Creating users

1. Enter username, display name, password, and role
2. Click **Create User**

Users are web app accounts — separate from **Drivers** (who are kart drivers linked to lap data).

### Deleting users

Click Delete next to any user. You cannot delete your own account.

---

## 11. Settings & Rules

Go to **Settings** in the sidebar.

### Competition Rules

Edit the EVGP rulebook values that drive compliance checking:

- **Max Current (A)** — hard-capped at 220A regardless of input
- **Speed Limit (km/h)**
- **Battery Voltage Max/Min (V)**
- **Battery Capacity (Wh)**
- **Min Combined Weight (kg)** — driver + kart
- **Rulebook Version** — label only (e.g. `2025-26`)

Click **Save Rules**. Changes take effect immediately for all future compliance checks.

### System Version

Shown at the top of Settings. This is the git short SHA of the deployed commit.

---

## 12. Running Tests

### On your laptop (before deploying to Pi)

```bash
# Activate venv first
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

bash scripts/run_tests.sh
```

This runs three things in sequence:
1. **pytest** — 8 test files covering auth, compliance, simulation, GPS, ML, analysis, storage, export, ingestion
2. **tsc --noEmit** — TypeScript type check of the entire frontend
3. **smoke_test.py** — starts a real uvicorn server on port 18000, registers an admin, uploads a synthetic CSV, asserts laps are created and Mode A simulation runs in < 500ms

All three must pass before you deploy to the Pi.

### Running tests individually

```bash
# All backend tests
pytest backend/tests/ -v

# One test file
pytest backend/tests/test_simulation.py -v

# Smoke test only
python scripts/smoke_test.py

# TypeScript type check
cd frontend && npx tsc --noEmit
```

---

## 13. Architecture Overview

```
Browser (any device on Wi-Fi hotspot)
        │ HTTP
        ▼
FastAPI (uvicorn, port 8000, single worker)
        │                    │
        ▼                    ▼
  SQLite (WAL mode)    React SPA (served as static files from /frontend/dist)
  strat-os.db
        │
        ├── Analysis pipeline (at upload time, not request time):
        │     data_loader → lap_analyzer → corner_detector → deep_analysis
        │     → GPS reconstruction → feature_extractor → ML training
        │
        └── Job queue (asyncio, polls every 500ms):
              ingest_csv, run_ml, simulation_c, export, reconstruct_track
```

**Key design decisions:**
- All analysis runs at **ingest time** — GET endpoints just read pre-computed results from SQLite, keeping all responses < 200ms on Pi
- **WAL mode** lets reads proceed while ingestion writes — no UI freezing
- **Single uvicorn worker** avoids SQLite write contention
- **No external APIs** — GPS reconstruction is pure math (equirectangular projection + Gaussian smooth), track map is Canvas API with no map tiles
- **No WebSocket** for replay — telemetry is preloaded, `requestAnimationFrame` drives animation, binary search finds current frame in O(log n)

---

## 14. API Reference

Full interactive docs always available at: `http://<pi-ip>:8000/docs`

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/system/status` | Health check + first-boot flag. No auth required. |
| `POST` | `/api/auth/login` | `{username, password}` → `{token, user}` |
| `POST` | `/api/auth/register` | First-boot only — creates admin user |
| `POST` | `/api/sessions/upload` | Multipart: `file` + `driver_id` + `kart_id` + `track_id` (all required) |
| `GET` | `/api/sessions/{id}/laps` | All laps for a session |
| `GET` | `/api/laps/{id}/telemetry?points=500` | Speed/time/GPS arrays, LTTB downsampled |
| `GET` | `/api/laps/{id}/sectors` | Sector splits |
| `GET` | `/api/laps/{id}/corners` | Corner entry/apex/exit speeds |
| `GET` | `/api/laps/{id}/energy` | Estimated energy consumption |
| `POST` | `/api/simulation/mode-a` | Synchronous linear simulation |
| `POST` | `/api/simulation/mode-c` | Queues physics ODE simulation job |
| `GET` | `/api/compliance/check` | Run compliance against active rules |
| `GET` | `/api/compliance/rules` | Get current rulebook values |
| `PUT` | `/api/compliance/rules` | Update rules (admin only) |
| `POST` | `/api/ml/train` | Queue ML training job |
| `GET` | `/api/ml/driver/{id}/style` | Driver style label + confidence |
| `GET` | `/api/storage/stats` | Disk usage + tier status |
| `POST` | `/api/export/session/{id}/report` | Queue export job (ZIP: charts + JSON + TXT) |
| `GET` | `/api/jobs/{id}` | Poll job status |

All routes except `/api/system/status`, `/api/auth/login`, and `/api/auth/register` require a `Bearer <token>` header.

---

## 15. Troubleshooting

### Service won't start on Pi

```bash
sudo journalctl -u strat-os -n 50
```

Common causes:
- Missing Python dependency — run `pip install -r backend/requirements.txt` in the venv
- Port 8000 already in use — check `sudo ss -tlnp | grep 8000`
- Database permission error — check `ls -la /home/pi/strat-os/data/`

### Browser can't reach strat-os.local

- Confirm you're connected to the `Strat-OS` Wi-Fi (not your home network)
- Try the IP directly: `http://192.168.73.1:8000`
- Check hostapd is running: `sudo systemctl status hostapd`

### CSV upload fails immediately

The upload endpoint requires all three: `driver_id`, `kart_id`, `track_id`. If any are missing it returns a 422 error. Create the entities first in their respective pages.

### Laps not detected after upload

- Check the job status at `/api/jobs/{id}` — the `error_msg` field will say what failed
- Verify the CSV is a genuine AiM export (Format line must say `AIM CSV`)
- The file must have at least a GPS Speed channel; GPS Latitude/Longitude are optional but needed for track maps

### Compliance shows VERIFY for everything

VERIFY means the system doesn't have enough data to confirm the rule — e.g. battery voltage was never recorded in telemetry. These items need manual inspection at scrutineering. Only FAIL items are automatic disqualifications.

### Mode A simulation returns an error

- The lap must have telemetry (time + speed arrays). If ingestion failed mid-way the lap row exists but telemetry may be missing.
- Check via `GET /api/laps/{id}/telemetry` — if it returns empty arrays, re-upload the session.

### ML style label never appears

- A driver needs at least 5 laps with feature vectors extracted before ML training is triggered
- Check the driver has laps: `GET /api/drivers/{id}/benchmarks`
- Manually trigger: `POST /api/ml/train` (via `/docs`)

### Storage page shows wrong disk usage

The storage stats read from the partition that contains `STRATOS_DATA_DIR`. On Pi this is the SD card. If your data directory is on a mounted network share the reported usage will be for the remote filesystem.

### Auto-update not running

```bash
sudo systemctl status strat-os-update
sudo journalctl -u strat-os-update -n 20
```

- If there's no internet the script exits silently (by design)
- If the git remote is unreachable (private repo without SSH keys) the fetch fails silently
- Manual update: `cd /home/pi/strat-os && git pull && sudo systemctl restart strat-os`
