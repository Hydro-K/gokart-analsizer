#!/usr/bin/env python3
"""
End-to-end smoke test for Strat-OS.
Starts a backend server on port 18000, runs key API flows, then tears down.
Works on Windows/macOS/Linux. Requires: httpx, uvicorn in the active venv.

Run: python scripts/smoke_test.py
"""
import os
import sys
import json
import math
import time
import signal
import subprocess
import threading
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

PORT = 18000
BASE = f"http://127.0.0.1:{PORT}/api"
ROOT = Path(__file__).parent.parent
TIMEOUT = 60  # seconds to wait for server startup

# ── Synthetic AiM CSV ─────────────────────────────────────────────────────────

def make_csv(n_laps=3):
    lines = [
        "Format,AIM CSV v2", "Device,EVO4S", "Vehicle,SmokeKart",
        "Driver,Smoke Driver", "Date,2024-03-01", "Time,09:00:00",
        "Session,Qualifying", "Channel,GPS Speed,GPS Latitude,GPS Longitude",
        "Units,km/h,deg,deg", "Frequency,10,10,10", "",
    ]
    t = 0.0
    for lap in range(n_laps):
        for step in range(600):
            lat = 51.5074 + 0.002 * math.sin(step * math.pi / 300)
            lon = -0.1278 + 0.002 * math.cos(step * math.pi / 300)
            spd = 40 + 20 * abs(math.sin(step * math.pi / 150))
            lines.append(f"{t:.1f},{spd:.1f},{lat:.6f},{lon:.6f}")
            t += 0.1
    return "\n".join(lines).encode()


# ── Helpers ───────────────────────────────────────────────────────────────────

def wait_for_server(max_secs=TIMEOUT):
    deadline = time.time() + max_secs
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE}/system/status", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  OK: {msg}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import tempfile, shutil

    data_dir = tempfile.mkdtemp(prefix="stratos_smoke_")
    env = {**os.environ, "STRATOS_DATA_DIR": data_dir, "STRATOS_DEBUG": "false"}

    print(f"Starting Strat-OS on port {PORT} (data: {data_dir})...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "127.0.0.1", "--port", str(PORT), "--no-access-log"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    def drain(stream, label):
        for line in stream:
            pass  # discard
    threading.Thread(target=drain, args=(proc.stdout, "stdout"), daemon=True).start()
    threading.Thread(target=drain, args=(proc.stderr, "stderr"), daemon=True).start()

    try:
        print("Waiting for server...")
        if not wait_for_server():
            print("ERROR: Server didn't start in time")
            proc.terminate()
            sys.exit(1)
        print("Server up.\n")

        c = httpx.Client(base_url=BASE, timeout=30)

        # 1. System status
        r = c.get("/system/status")
        check(r.status_code == 200, "GET /system/status returns 200")
        check(r.json()["first_boot"] is True, "first_boot = True on fresh DB")

        # 2. Register admin (first boot)
        r = c.post("/auth/register", json={
            "username": "smoke_admin", "display_name": "Smoke Admin",
            "password": "smokepass", "role": "admin",
        })
        check(r.status_code == 200, "POST /auth/register creates admin")
        token = r.json()["token"]
        h = {"Authorization": f"Bearer {token}"}

        # 3. First boot cleared
        r = c.get("/system/status")
        check(r.json()["first_boot"] is False, "first_boot = False after admin created")

        # 4. Create entities
        r = c.post("/drivers", json={"name": "Smoke Driver", "notes": ""}, headers=h)
        check(r.status_code == 200, "Create driver")
        driver_id = r.json()["id"]

        r = c.post("/karts", json={"name": "Smoke Kart"}, headers=h)
        check(r.status_code == 200, "Create kart")
        kart_id = r.json()["id"]

        r = c.post("/tracks", json={"name": "Smoke Track"}, headers=h)
        check(r.status_code == 200, "Create track")
        track_id = r.json()["id"]

        # 5. Upload CSV
        csv_bytes = make_csv(n_laps=3)
        r = c.post("/sessions/upload",
                   files={"file": ("smoke.csv", csv_bytes, "text/csv")},
                   data={"driver_id": str(driver_id), "kart_id": str(kart_id),
                         "track_id": str(track_id), "session_type": "Qualifying"},
                   headers=h)
        check(r.status_code == 200, "CSV upload accepted")

        # 6. Poll until ingestion done (max 30s)
        job_id = r.json().get("job_id")
        session_id = r.json().get("session_id")
        if job_id:
            deadline = time.time() + 30
            while time.time() < deadline:
                jr = c.get(f"/jobs/{job_id}", headers=h)
                status = jr.json().get("status", "")
                if status == "done":
                    session_id = jr.json().get("result_json") and json.loads(jr.json()["result_json"]).get("session_id")
                    break
                if status == "failed":
                    check(False, f"Ingestion job failed: {jr.json().get('error_msg')}")
                time.sleep(1)

        if session_id:
            # 7. Verify laps created
            r = c.get(f"/sessions/{session_id}/laps", headers=h)
            check(r.status_code == 200, "GET session laps")
            laps = r.json()
            check(len(laps) >= 1, f"At least 1 lap created (got {len(laps)})")

            valid = [l for l in laps if l.get("is_valid")]
            if valid:
                best = min(valid, key=lambda x: x["lap_time_s"])
                check(best["lap_time_s"] < 120, f"Best lap < 120s (got {best['lap_time_s']:.1f})")

            # 8. Compliance check
            r = c.get(f"/sessions/{session_id}/compliance", headers=h)
            check(r.status_code == 200, "Compliance check returns 200")
            check("overall" in r.json(), "Compliance result has 'overall'")

        # 9. Mode A simulation (if we have a lap)
        if session_id:
            r2 = c.get(f"/sessions/{session_id}/laps", headers=h)
            laps2 = [l for l in r2.json() if l.get("is_valid")]
            if laps2:
                t0 = time.time()
                r3 = c.post("/simulation/mode-a", json={
                    "lap_id": laps2[0]["id"],
                    "max_current": 200,
                    "accel_rate": 1.0,
                    "speed_limit_pct": 100,
                }, headers=h)
                elapsed = (time.time() - t0) * 1000
                check(r3.status_code == 200, "Mode A simulation returns 200")
                check(elapsed < 500, f"Mode A simulation < 500ms (got {elapsed:.0f}ms)")

        # 10. 220A hard limit
        from backend.schemas import SimModeARequest
        req = SimModeARequest(lap_id=1, max_current=250)
        check(req.max_current == 220, "Pydantic caps 250A → 220A")

        print("\n=== All smoke tests passed ===\n")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
