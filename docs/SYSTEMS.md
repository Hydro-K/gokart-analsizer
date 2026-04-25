# Strat-OS — How Every System Works

This document explains the internal mechanics of each Strat-OS subsystem: what it does, how it does it, and how to use it correctly. Intended for team engineers, developers maintaining the codebase, and anyone who wants to understand what's happening under the hood.

---

## Table of Contents

1. [Data Ingestion Pipeline](#1-data-ingestion-pipeline)
2. [Lap Analysis Engine](#2-lap-analysis-engine)
3. [GPS Track Reconstruction](#3-gps-track-reconstruction)
4. [Simulation System](#4-simulation-system)
5. [Compliance Checker](#5-compliance-checker)
6. [ML Driver Style Classifier](#6-ml-driver-style-classifier)
7. [Job Queue](#7-job-queue)
8. [Storage Management](#8-storage-management)
9. [Authentication & Users](#9-authentication--users)
10. [Database Schema](#10-database-schema)
11. [Frontend Architecture](#11-frontend-architecture)
12. [API Layer](#12-api-layer)
13. [Raspberry Pi Infrastructure](#13-raspberry-pi-infrastructure)

---

## 1. Data Ingestion Pipeline

**Files:** `backend/services/ingestion.py`, `backend/analysis/data_loader.py`, `backend/analysis/lap_analyzer.py`

### What it does

When you upload a CSV file, the ingestion pipeline converts raw AiM telemetry into every derived data product the system needs — laps, telemetry, sectors, corners, GPS maps, ML features, and benchmark times. This all happens once at upload time, so every subsequent GET request is just a database read.

### Step-by-step

```
CSV upload
    │
    ▼
data_loader.load_aim_csv()
    Parse header metadata (driver, kart, date, session type)
    Read channel columns (GPS Speed, Latitude, Longitude, ...)
    Detect lap markers or use speed-threshold lap splitting
    ↓
lap_analyzer.analyse_session()
    For each lap:
      corner_detector.detect_corners() → CornerResult list
      Compute lap time, validity (< 3× median = valid)
      Classify phase at each sample: accelerating / braking / cornering / straight
    ↓
_persist_laps()
    INSERT INTO laps (lap_number, lap_time_s, is_valid, driver_id, kart_id, track_id)
    INSERT INTO lap_telemetry (time_json, speed_json, lat_json, lon_json, phase_json)
    ↓
_extract_ml_features()
    For each lap: extract_features(lap) → 5 floats
    INSERT INTO feature_vectors
    ↓
_rebuild_track_gps()
    If GPS data present: reconstruct_track(lat, lon) → local_xy
    UPDATE tracks SET local_xy=..., length_m=...
    ↓
_update_benchmarks()
    Compute theoretical best lap (sum of best sector per lap)
    UPDATE benchmarks (best_ever_s, best_session_s, theoretical_best_s)
    ↓
Auto-trigger ML job if driver has ≥ 5 laps with features
```

### What triggers ingestion

`POST /api/sessions/upload` creates a job of type `ingest_csv` in the jobs table. The async job runner picks it up within 500ms and runs the full pipeline in a worker thread (so the event loop stays responsive).

### Required fields

The upload endpoint **blocks** if `driver_id`, `kart_id`, or `track_id` are missing. This is intentional — laps are always linked to all three entities so filtering and benchmarking work correctly.

### Error handling

Each step is wrapped in try/except with `log.warning()`. If GPS reconstruction fails (e.g. no GPS columns in the CSV), laps are still created without a track map. If feature extraction fails for a lap, that lap gets no ML entry but others succeed.

---

## 2. Lap Analysis Engine

**Files:** `backend/analysis/lap_analyzer.py`, `backend/analysis/corner_detector.py`, `backend/analysis/deep_analysis.py`

### LapData object

Every piece of analysis works from a `LapData` dataclass:

```python
@dataclass
class LapData:
    lap_number: int
    start_idx: int       # index into raw telemetry arrays
    end_idx: int
    lap_time: float      # seconds
    time: np.ndarray     # seconds from lap start
    speed: np.ndarray    # m/s
    lat: np.ndarray      # GPS latitude (may be empty)
    lon: np.ndarray      # GPS longitude (may be empty)
    phase: np.ndarray    # 'accelerating'|'braking'|'cornering'|'straight'
    corners: List[CornerResult]  # detected corners
```

### Phase classification

Each sample is classified by looking at the smoothed acceleration:

| Phase | Condition |
|-------|-----------|
| `accelerating` | accel > +0.3 m/s² |
| `braking` | accel < −0.3 m/s² |
| `cornering` | speed < local min + 20% AND lateral g > threshold |
| `straight` | everything else |

Phase arrays are stored as JSON in `lap_telemetry.phase_json` and returned with telemetry for frontend colouring.

### Corner detection

`corner_detector.detect_corners()` uses speed minima as apex candidates:
1. Apply Gaussian smooth (σ=3) to speed
2. Find local minima with `scipy.signal.find_peaks(−speed, prominence=2.0)`
3. For each apex: walk backward to find entry (speed rising from left), walk forward to find exit
4. Compute `entry_speed`, `apex_speed`, `exit_speed`, `radius_m` (from centripetal acceleration)

### Sector splits

`deep_analysis.sector_splits(lap, n_sectors=5)` divides the lap by **distance** (not time) into equal segments and returns time, min/max speed for each. Used for theoretical best calculation and the sector display on the frontend.

### Energy estimation

`deep_analysis.estimate_energy(time, speed)`:
```
P_motor = F_total × v
F_total = rolling_resistance + aero_drag + accel_force
E = ∫P dt / 3,600,000  [kWh]
```
Uses default vehicle parameters (mass=115 kg, Cd=0.5, A=0.6 m², Crr=0.015). These match the EVGP kart spec closely enough for relative comparisons between laps.

### Smoothness score

`deep_analysis.driver_smoothness_score(time, speed)`:
```
jerk = d/dt (acceleration)
RMS_jerk = sqrt(mean(jerk²))
score = max(0, 100 − RMS_jerk × 5)
```
A perfectly smooth speed profile scores 100. Aggressive braking/throttle inputs push the score toward 0.

### Theoretical best lap

Computed inline in the ingestion pipeline by taking the **best time for each sector across all laps in the session** and summing them:

```
theo_best = Σ min(sector_s_time[lap] for lap in all_laps) for s in 1..5
```

This represents the fastest possible time if the driver achieved their best performance in every sector simultaneously. It's always ≤ the actual best lap.

---

## 3. GPS Track Reconstruction

**File:** `backend/analysis/gps_reconstruction.py`

### Why offline?

No map tile APIs, no internet. The track shape comes entirely from the GPS coordinates embedded in the AiM CSV.

### Algorithm

```python
def reconstruct_track(lat, lon, smooth_sigma=15.0) -> TrackMap:
```

1. **Filter GPS outliers** — drop any point > 50 m from the previous point (GPS glitches)
2. **Remove duplicates** — drop points < 0.5 m apart (stationary car at start/finish)
3. **Equirectangular projection** to local XY metres:
   ```
   x = R × radians(lon − lon_center) × cos(radians(lat_center))
   y = R × radians(lat − lat_center)
   ```
   This is accurate to < 0.1% for tracks up to 5 km in size.
4. **Gaussian smooth** (σ=15 samples) to remove GPS jitter. On a 10 Hz system at 50 km/h, each sample is ~1.4 m, so σ=15 ≈ 21 m smoothing window — enough to clean noise without rounding corners.
5. **Compute track length** from cumulative segment distances.
6. **Normalize to 0–1000 canvas units** preserving aspect ratio (50 px margin each side).

### Output

```python
@dataclass
class TrackMap:
    local_xy: List[List[float]]  # [[x, y], ...] in 0-1000 range
    lat_center: float
    lon_center: float
    length_m: float
```

Stored as JSON text in `tracks.local_xy`. The frontend renders it directly on a Canvas element without any map library.

### When it runs

- Automatically during ingestion if GPS columns exist in the CSV
- Can be manually re-triggered via `POST /api/tracks/{id}/reconstruct` which queues a `reconstruct_track` job using GPS data from the best lap on that track

---

## 4. Simulation System

**File:** `backend/analysis/simulation.py`

### The 220A hard limit

```python
_MAX_CURRENT = 220  # EVGP rule — enforced in 3 places

def simulate_mode_a(lap, max_current, ...):
    max_current = min(max_current, _MAX_CURRENT)  # enforced here
```

Also enforced in `backend/schemas.py`:
```python
@field_validator("max_current")
def cap_current(cls, v): return min(v, 220)
```

And in `backend/analysis/recommendations.py`:
```python
_MAX_CURRENT_LIMIT = 220
```

### Mode A — Fast Linear Simulation

**Route:** `POST /api/simulation/mode-a`  
**Response time:** < 100ms

Mode A answers: *"What would this lap look like with different settings?"*

It takes the actual recorded speed profile and applies perturbations:

```python
# 1. Apply current-based acceleration factor
accel_factor = (max_current / reference_current) * accel_rate

# 2. Apply speed limit cap
speed_cap = max_speed * (speed_limit_pct / 100)

# 3. Apply gear ratio change (affects top speed and acceleration balance)
gear_factor = gear_ratio_old / gear_ratio_new

# 4. Apply mass change (affects acceleration in non-constant-speed phases)
mass_factor = sqrt(mass_old / mass_new)

# 5. Scale time axis where speed changes are occurring
# Straight sections: multiply by gear_factor × mass_factor
# Braking sections: multiply by inverse of accel_factor
# Cornering: unchanged (limited by tyres, not motor)
```

Returns:
- `delta_lap_time_s` — positive = slower, negative = faster
- `predicted_lap_time_s` — actual estimated time
- `delta_points` — cumulative time delta at each sample point (for the delta chart)
- `energy_delta_kwh` — estimated energy change

### Mode C — Physics ODE Simulation

**Route:** `POST /api/simulation/mode-c`  
**Creates an async job, typically 2-5s on Pi**

Mode C solves the full equations of motion using `scipy.integrate.solve_ivp` with the RK23 solver. State vector: `[x, v, E]` (position, velocity, energy consumed).

```
dx/dt = v
dv/dt = (F_motor − F_drag − F_roll − F_brake) / mass
dE/dt = P_motor / 3,600,000
```

Motor force is looked up from a torque curve that approximates the Alltrax controller:
```python
# Alltrax SPM characteristic: constant torque to ~60% of no-load RPM, then falls off
F_motor = min(current × kt × gear_ratio / wheel_radius,
              mass × 9.81 × 0.3)  # traction limit
```

The driver phase from the real lap is replayed to decide whether the simulated car is accelerating, braking, or coasting at each point. This means Mode C predicts what the physics would do if the driver drove the same line with different hardware.

### Goal parameter

Mode C accepts `goal: 'lap_time' | 'energy' | 'balanced'` and `weight_speed`/`weight_energy`:

```
score = weight_speed × (lap_time_improvement) + weight_energy × (energy_saving)
```

The returned result includes the score alongside the raw numbers.

---

## 5. Compliance Checker

**Files:** `backend/analysis/competition_rules.py`, `backend/routers/compliance.py`

### Rule storage

Rules live in the `competition_rules` table (always a single row, id=1). They are loaded into a `CompetitionRules` dataclass on each check:

```python
@dataclass
class CompetitionRules:
    controller_max_current_a: float = 220.0
    battery_voltage_max_v: float = 58.4
    battery_voltage_min_v: float = 40.0
    battery_capacity_wh: float = 3072.0
    speed_limit_kmh: float = 80.0
    combined_min_weight_kg: float = 181.4
    rulebook_version: str = "2025-26"
    # ... plus allowed controller models, tyre spec, safety items
```

### What gets checked

`ComplianceChecker.check(settings, gear)` runs these checks:

| Check | Source | Rule |
|-------|--------|------|
| Max controller current | `AlltraxSettings.max_current` | ≤ 220A |
| Hi-voltage cutoff | `AlltraxSettings.hi_voltage_cutoff` | ≤ 58.4V |
| Lo-voltage cutoff | `AlltraxSettings.lo_voltage_cutoff` | ≥ 40.0V |
| Theoretical top speed | Computed from `GearRatioConfig` | ≤ 80 km/h |
| Combined weight | `kart.mass_kg + 67` (avg driver) | ≥ 181.4 kg |
| Controller model | Cannot auto-detect | VERIFY |
| Tyre compound | Cannot auto-detect | VERIFY |
| Safety equipment | Cannot auto-detect | VERIFY × 4 |

### Status meanings

| Status | Meaning |
|--------|---------|
| `PASS` | Within rule limits — no action needed |
| `FAIL` | **Rule violation** — fix before racing |
| `WARN` | Within limits but within 5% of the limit — worth monitoring |
| `VERIFY` | Cannot be checked in software — confirm manually at scrutineering |

### Using compliance

**From a session:** Click any session → the compliance panel at the bottom shows the result for the kart used in that session.

**Standalone:** Compliance page → results shown for all currently configured karts. Use `?session=<id>` in the URL to check a specific session.

**Updating rules:** Settings page → Competition Rules section. Changes take effect immediately. The 220A cap cannot be raised beyond 220 regardless of what you enter.

---

## 6. ML Driver Style Classifier

**Files:** `backend/analysis/ml/feature_extractor.py`, `backend/analysis/ml/clustering.py`, `backend/analysis/ml/model_store.py`

### Overview

The ML system classifies each driver as `aggressive`, `smooth`, `balanced`, or `inconsistent` purely from telemetry — no manual labelling required. It learns incrementally as more laps are uploaded.

### Feature extraction

Five features are extracted per lap. All values are bounded 0–100:

| Feature | How computed | What it measures |
|---------|-------------|-----------------|
| `throttle_variance` | `std(acceleration) / mean(acceleration) × 10` during accelerating phases | How smoothly the driver applies throttle |
| `braking_intensity` | `mean(|deceleration|) / 10 × 100` during braking phases | How hard the driver brakes |
| `corner_entry_speed_avg` | Average speed 0.5s before each apex | How late and fast the driver enters corners |
| `accel_consistency` | `100 − CV(exit_acceleration_per_corner) × 20` | How consistently the driver exits corners |
| `smoothness_score` | RMS jerk score (from `driver_smoothness_score`) | Overall smoothness of inputs |

### Bootstrap phase (< 20 laps)

```python
km = MiniBatchKMeans(n_clusters=4, n_init=3)
raw_labels = km.fit_predict(X_scaled)
cluster_map = _map_clusters_to_labels(km, scaler, X_scaled)
```

Cluster centroids are examined and mapped to style labels by scoring each centroid:
- **Aggressive** = high braking_intensity + high throttle_variance + low accel_consistency
- **Smooth** = high smoothness + high accel_consistency + low throttle_variance
- **Inconsistent** = high throttle_variance + low accel_consistency + low smoothness
- **Balanced** = whichever centroid scores lowest on the above

### Incremental phase (≥ 20 laps)

```python
clf = SGDClassifier(loss='log_loss', random_state=42)
clf.partial_fit(X_scaled, bootstrap_labels, classes=_STYLE_LABELS)
```

`partial_fit` updates the classifier with each new batch without re-training from scratch. This is important for Pi performance — a full re-fit of 500 laps would be slow, but `partial_fit` on 10 new laps takes milliseconds.

### Driver-level style

After per-lap labels are assigned, the driver's overall style is determined by majority vote with **recent laps weighted 2×**:

```python
recent = labels[max(0, n - n//3):]  # last third
weighted = labels + recent           # recent counted twice
style = Counter(weighted).most_common(1)[0][0]
confidence = count / total × 100
```

### Model persistence

Models are saved to `data/models/` using joblib:
- `scaler.joblib` — StandardScaler fitted to all feature vectors
- `kmeans.joblib` — bootstrap cluster model
- `classifier.joblib` — incremental SGDClassifier (replaces kmeans after 20 laps)
- `model_meta.json` — last trained timestamp and sample count

### Auto-trigger

After every ingestion, if the driver now has ≥ 5 laps with feature vectors, a `run_ml` job is auto-submitted to the job queue.

---

## 7. Job Queue

**File:** `backend/services/job_runner.py`

### Why a job queue?

Some operations (CSV ingestion, Mode C simulation, ML training, export) take 1–30 seconds. FastAPI is async — running these synchronously would block all other requests during that time. The job queue offloads them to a background asyncio task.

### Architecture

```python
# Startup (in main.py lifespan)
asyncio.create_task(start_job_runner())

# Loop runs every 500ms
async def run_forever(poll_interval=0.5):
    while True:
        await asyncio.sleep(poll_interval)
        await _process_next()
```

`_process_next()` claims the highest-priority pending job using an UPDATE with WHERE clause (atomic claim — safe for concurrent workers if laptop offload is used):

```sql
UPDATE jobs SET status='running', worker_id=?, updated_at=...
WHERE id = (
    SELECT id FROM jobs WHERE status='pending'
    ORDER BY priority ASC, created_at ASC LIMIT 1
)
```

### Job types

| Type | Handler | Typical duration |
|------|---------|-----------------|
| `ingest_csv` | `_handle_ingest` | 2–10s |
| `run_ml` | `_handle_ml` | 0.5–3s |
| `simulation_c` | `_handle_simulation_c` | 2–5s |
| `export` | `_handle_export` | 3–8s |
| `reconstruct_track` | `_handle_reconstruct` | 0.5–2s |

### Priority

Lower number = higher priority:
- 1 = export (user is waiting for download)
- 3 = simulation_c
- 5 = ingest_csv (default)
- 7 = run_ml (background)
- 9 = reconstruct_track (low urgency)

### Laptop offload

If a `laptop_worker.py` is running on another machine on the network, it can claim `simulation_c` jobs via `GET /api/jobs/pending/count` + `PUT /api/jobs/{id}/claim`. The `worker_id` field distinguishes Pi jobs from laptop jobs. The Pi always functions standalone — the laptop just accelerates heavy computation.

### Polling a job

```
GET /api/jobs/{id}
→ { "status": "pending"|"running"|"done"|"failed",
    "result_json": "...",   // JSON string with result data
    "error_msg": "..." }    // populated if failed
```

The frontend `useJobPoller` hook polls this every 1.5 seconds until `status === 'done'` or `'failed'`.

---

## 8. Storage Management

**File:** `backend/services/storage_manager.py`

### Tier model

Strat-OS uses a **two-tier** storage model:

| Tier | Location | Content |
|------|----------|---------|
| Primary | SD card (`data/`) | Everything: DB, uploads, exports, models |
| Archive | Network SMB or Google Drive | Raw CSV files only |

SQLite rows, lap telemetry, and export files always stay on the primary tier. Only raw uploaded CSV files are archived — the analysis is already in the database.

### Thresholds

| SD usage | Action |
|----------|--------|
| < 70% | OK — nothing happens |
| 70–80% | Warning badge in sidebar storage bar |
| 80–90% | Auto-archive: raw CSVs moved to archive backend (keep 2 most recent per driver) |
| > 90% | Emergency: raw CSVs already archived are deleted from archive storage too |

### Archive backends

```python
# config.py
ARCHIVE_BACKEND = os.getenv("STRATOS_ARCHIVE_BACKEND", "disabled")
# options: "disabled" | "local" | "smb" | "rclone_gdrive"
```

**SMB (network share):**
```bash
STRATOS_ARCHIVE_BACKEND=smb
STRATOS_SMB_SHARE=//192.168.73.50/kartarchive
```
Uses `subprocess.run(['cp', src, smb_path])` after the share is mounted. The Pi's `setup.sh` installs `cifs-utils` for SMB support.

**Google Drive (rclone):**
```bash
STRATOS_ARCHIVE_BACKEND=rclone_gdrive
STRATOS_RCLONE_REMOTE=gdrive:strat-os-archive
```
Only runs when `ping -c 1 8.8.8.8` succeeds. The Pi's `setup.sh` installs rclone. You must configure the rclone remote separately (`rclone config`).

**Best-effort:** If the archive backend is unreachable, the job stays `pending` in the jobs table with type `archive` and retries on the next auto-cleanup cycle. The Pi never halts because of a failed archive.

### Getting stats

```
GET /api/storage/stats
→ {
    "total_gb": 32.0, "used_gb": 18.5, "free_gb": 13.5, "used_pct": 57.8,
    "status": "ok",
    "thresholds": {"warn": 70, "critical": 80, "emergency": 90},
    "archive_backend": "smb"
  }
```

---

## 9. Authentication & Users

**Files:** `backend/routers/auth.py`, `backend/routers/users.py`

### Token-based auth

No JWT. Tokens are 32-byte URL-safe random strings stored in the `auth_tokens` table with an expiry timestamp. This keeps everything in SQLite — no external services needed offline.

```sql
CREATE TABLE auth_tokens (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL   -- ISO 8601, UTC
);
```

Default expiry: 30 days (configurable via `STRATOS_TOKEN_EXPIRE_HOURS`).

### Roles

| Role | What they can do |
|------|----------------|
| `admin` | Everything: create/delete users, edit competition rules, archive sessions |
| `engineer` | Upload sessions, create/edit drivers/karts/tracks, all read access |
| `viewer` | Read-only access to all data, no uploads or edits |

### First boot

On a fresh database `GET /api/system/status` returns `"first_boot": true`. The frontend redirects to `/wizard`. The wizard calls `POST /api/auth/register` which creates the first admin account. Once any user exists, `/auth/register` returns 403 — all subsequent users are created by an admin via `/api/users`.

### Password storage

Passwords are hashed with bcrypt (work factor 12). The `password_hash` column is never returned by any API endpoint.

### Users vs Drivers

**Important distinction:**

- **Users** = team members who log into the web app (have passwords, roles)
- **Drivers** = people who drive the kart (linked to laps and telemetry data)

The same person can be both a User and a Driver, but they are separate records. A Driver entity has no login capability — it's purely a data entity for lap attribution.

---

## 10. Database Schema

**File:** `backend/database.py`

SQLite with WAL mode for concurrent read/write. All 16 tables:

```
users              ← web app accounts (login, roles)
auth_tokens        ← session tokens
drivers            ← kart drivers (data entities)
karts              ← kart configurations
tracks             ← track definitions + GPS map
sessions           ← each track day / session
laps               ← individual laps (FK: session, driver, kart, track)
lap_telemetry      ← time/speed/gps/phase arrays stored as JSON text
feature_vectors    ← 5 ML features per lap
driver_styles      ← ML style label per driver (one row per driver)
kart_setups        ← historical Alltrax settings per session
post_session_readings ← tyre temps/PSI, motor/battery temps after session
simulation_results ← saved Mode A and Mode C outputs
benchmarks         ← best ever / session / theoretical per driver+kart+track
jobs               ← async job queue
storage_archive    ← audit log of what has been archived and where
competition_rules  ← single row (id=1) — EVGP rulebook values
```

### Key design choices

**Laps carry all 4 FKs** (session, driver, kart, track) even though session already implies driver/kart/track. This allows fast filtering queries like "all laps for driver X on track Y" without a join through sessions.

**Telemetry as JSON text**: Storing arrays as `[0.0, 0.1, 0.2, ...]` text instead of binary makes the database human-inspectable with sqlite3 CLI. At 10 Hz for 60-second laps, a full telemetry row is ~4 KB — acceptable for SQLite.

**WAL mode**: `PRAGMA journal_mode=WAL` allows readers to continue while the writer is active. This prevents the UI from freezing during CSV ingestion.

**Single competition_rules row**: Always id=1, never deleted. `INSERT OR IGNORE INTO competition_rules (id) VALUES (1)` in the DDL seeds it. Updates use `UPDATE WHERE id=1`. This avoids any "which rules are active?" ambiguity.

---

## 11. Frontend Architecture

**Directory:** `frontend/src/`

### Routing

`main.tsx` checks `GET /api/system/status` on load:
- If `first_boot: true` → show Wizard (no auth required)
- If no token in localStorage → redirect to `/login`
- Otherwise → render the full AppShell with sidebar

### State management (Zustand)

Two stores:

**`authStore`** (persisted to localStorage):
```typescript
{ token: string | null, user: User | null }
setAuth(token, user)  // called after login
clearAuth()           // called on logout
```

**`uiStore`** (persisted to localStorage):
```typescript
{ mode: 'beginner' | 'engineer' }
toggleMode()
```

### API layer (`src/api/`)

All API calls go through `src/api/client.ts` which:
1. Reads the Bearer token from localStorage
2. Attaches it as `Authorization: Bearer <token>`
3. Handles 401 → clears token + redirects to `/login`
4. Handles non-OK → throws `Error(detail)` from the JSON response

```typescript
// Usage in any component:
const drivers = await api.get<Driver[]>('/drivers')
const res = await api.post<{job_id: number}>('/sessions/upload', form)
```

### Beginner/Engineer mode

Components check `const mode = useUIStore(s => s.mode)` and conditionally render:

- **Beginner hides**: corner analysis table, energy estimate, sector heatmap, Mode C simulation, raw compliance JSON
- **Beginner shows**: colour-coded badges, plain-English metric cards, simplified lap table, highlighted best lap star

Toggle is in the sidebar bottom. Persisted across sessions via localStorage.

### TrackCanvas (dual-layer)

```
<div style="position:relative">
  <canvas ref={trackRef}  />  ← bottom layer: track outline, drawn once
  <canvas ref={dotRef}    />  ← top layer:    animated dot, cleared each frame
</div>
```

The track layer is drawn once when `xy` changes. The dot layer is cleared and redrawn every `requestAnimationFrame` tick during replay. This prevents expensive full-canvas redraws on every frame.

Track outline is drawn from `local_xy` (0–1000 normalized coordinates) scaled to fit the canvas. No map library — pure Canvas 2D API.

### Job polling

`useJobPoller(jobId, intervalMs=1500)` uses `setInterval` to poll `GET /api/jobs/{id}` until `status === 'done'` or `'failed'`, then clears the interval. The `<JobProgress>` component wraps this with a spinner and status badge.

---

## 12. API Layer

**Directory:** `backend/routers/`

All routes require `Authorization: Bearer <token>` except:
- `GET /api/system/status` — health check, first-boot detection
- `POST /api/auth/login`
- `POST /api/auth/register` (only works when no users exist)

### Response conventions

- Success: HTTP 200 with JSON body
- Created: HTTP 200 (not 201 — simpler client code)
- Not found: HTTP 404 `{"detail": "..."}`
- Validation error: HTTP 422 (Pydantic)
- Auth error: HTTP 401 or 403
- Conflict (e.g. delete with FK): HTTP 409

### LTTB downsampling

Telemetry endpoints accept `?points=N` to downsample using the Largest Triangle Three Buckets algorithm:

```
GET /api/laps/{id}/telemetry?points=500
```

This keeps the 500 most visually significant points from potentially thousands of samples. On a Pi browser, 500 points renders Recharts at 60fps; 3,000+ points causes stuttering.

### Session uploads

`POST /api/sessions/upload` is a multipart form:
```
file: <CSV binary>
driver_id: 1
kart_id: 1  
track_id: 1
session_type: "Practice 1"
```

Returns immediately with `{"job_id": 42}`. The actual ingestion happens in the job runner.

### Simulation endpoints

**Mode A (sync):**
```
POST /api/simulation/mode-a
{
  "lap_id": 15,
  "max_current": 200,      ← capped to 220 by Pydantic
  "accel_rate": 1.1,
  "speed_limit_pct": 100,
  "gear_ratio_new": 8.2,
  "gear_ratio_old": 8.0,
  "mass_new_kg": 115.0
}
→ { "delta_lap_time_s": -0.42, "predicted_lap_time_s": 61.3, ... }
```

**Mode C (async):**
```
POST /api/simulation/mode-c
{ "lap_id": 15, "session_id": 3, "max_current": 200, "goal": "balanced", ... }
→ { "job_id": 87 }
```

---

## 13. Raspberry Pi Infrastructure

**Files:** `scripts/setup.sh`, `scripts/auto_update.sh`, `strat-os.service`

### Network topology

```
Raspberry Pi 4
├── wlan0 (hotspot) ← team devices connect here
│   SSID: Strat-OS | IP: 192.168.73.1
│   DHCP: 192.168.73.10 – .50
├── eth0 (optional) ← internet for updates / rclone
└── uvicorn on :8000 ← serves both API and React SPA
```

There is no screen on the Pi. All interaction is through the browser on any connected device (phone, tablet, laptop).

### Service management

```bash
# Check status
sudo systemctl status strat-os

# View logs (live)
sudo journalctl -u strat-os -f

# Restart
sudo systemctl restart strat-os

# Check auto-update log
cat /var/log/strat-os-update.log
```

### Auto-update sequence (every boot)

```
boot
  → strat-os-update.service starts (Before=strat-os.service)
      → ping 8.8.8.8
          FAIL → exit 0 (offline, skip)
          PASS → git fetch origin main
              → LOCAL == REMOTE → exit 0 (up to date)
              → NEW COMMITS → git pull → pip install → npm build → systemctl restart
  → strat-os.service starts (uvicorn)
```

### Environment variables

All configuration is via environment variables in the systemd unit:

```ini
[Service]
Environment=STRATOS_PI_MODE=true
Environment=STRATOS_DATA_DIR=/home/pi/strat-os/data
Environment=STRATOS_ARCHIVE_BACKEND=smb
Environment=STRATOS_SMB_SHARE=//192.168.73.50/kartarchive
Environment=STRATOS_TOKEN_EXPIRE_HOURS=720
```

Edit with: `sudo systemctl edit strat-os` (creates an override file).

### Performance targets on Pi 4

| Operation | Target | How achieved |
|-----------|--------|-------------|
| GET requests | < 200ms | Pre-computed at ingest, single SELECT per endpoint |
| CSV ingestion | 2–10s | Async job, doesn't block UI |
| Mode A simulation | < 100ms | Synchronous, pure NumPy |
| Mode C simulation | 2–5s | Async job with RK23 ODE |
| Telemetry chart render | 60fps | LTTB downsample to ≤ 500 points |
| Track map draw | < 16ms | Canvas API, no map library |

### SD card longevity

SQLite WAL mode reduces write amplification compared to default journal mode. The data directory should be on the SD card's main partition (not a RAM disk) so data survives power cuts at the track. The auto-cleanup system prevents the SD from filling up — at 90% usage it enters emergency mode and removes old raw files.
