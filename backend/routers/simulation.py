"""Simulation endpoints — Mode A (sync) and Mode C (async job)."""
from __future__ import annotations
import json
import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import SimInputA, SimResultA, SimInputC, SimResultJobOut
import backend.config as cfg

router = APIRouter(tags=["simulation"])


@router.post("/mode-a", response_model=SimResultA)
def simulate_mode_a(body: SimInputA, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    from backend.analysis.simulation import simulate_mode_a as _sim_a
    tel = db.execute("SELECT * FROM lap_telemetry WHERE lap_id=?", (body.lap_id,)).fetchone()
    lap_row = db.execute("SELECT lap_time_s FROM laps WHERE id=?", (body.lap_id,)).fetchone()
    if not tel or not lap_row:
        raise HTTPException(404, "Lap not found")
    import numpy as np
    time_arr  = np.array(json.loads(tel["time_json"]))
    speed_arr = np.array(json.loads(tel["speed_json"]))
    phase_arr = json.loads(tel["phase_json"]) if tel["phase_json"] else []
    from backend.analysis.lap_analyzer import LapData
    lap = LapData(lap_number=0, start_idx=0, end_idx=len(time_arr)-1,
                  lap_time=lap_row["lap_time_s"], time=time_arr, speed=speed_arr,
                  phase=phase_arr)
    sim_speed, sim_time = _sim_a(
        lap=lap,
        max_current=body.max_current,
        accel_rate=body.accel_rate,
        speed_limit_pct=body.speed_limit_pct,
        gear_ratio_new=body.gear_ratio_new,
        gear_ratio_old=body.gear_ratio_old,
        mass_new_kg=body.mass_new_kg,
        mass_old_kg=body.mass_old_kg,
        tyre_psi_rear=body.tyre_psi_rear,
        tyre_psi_front=body.tyre_psi_front,
        motor_temp_c=body.motor_temp_c,
    )
    orig = lap_row["lap_time_s"]
    delta = sim_time - orig
    return SimResultA(
        original_lap_time_s=round(orig, 3),
        simulated_lap_time_s=round(sim_time, 3),
        delta_s=round(delta, 3),
        delta_pct=round(delta / orig * 100, 2) if orig else 0.0,
        energy_kwh=None,
        inputs=body,
    )


@router.post("/mode-c", response_model=SimResultJobOut)
def simulate_mode_c(body: SimInputC, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM laps WHERE id=?", (body.lap_id,)).fetchone():
        raise HTTPException(404, "Lap not found")
    cur = db.execute(
        "INSERT INTO jobs(type, priority, payload_json) VALUES(?,?,?)",
        ("simulation_c", 3, body.model_dump_json()),
    )
    return SimResultJobOut(job_id=cur.lastrowid)


@router.get("/results/{session_id}")
def list_results(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(
        "SELECT * FROM simulation_results WHERE session_id=? ORDER BY created_at DESC",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]
