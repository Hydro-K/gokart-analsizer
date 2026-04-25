"""Async SQLite-backed job queue runner."""
from __future__ import annotations
import asyncio
import json
import logging
import uuid
from typing import Callable

log = logging.getLogger(__name__)

_WORKER_ID = f"pi-{uuid.uuid4().hex[:8]}"


async def run_forever(poll_interval: float = 0.5) -> None:
    """Main job loop — runs as a background asyncio task."""
    from backend.database import get_db
    while True:
        await asyncio.sleep(poll_interval)
        try:
            await _process_next()
        except Exception as e:
            log.error("Job runner error: %s", e)


async def _process_next() -> bool:
    from backend.database import create_connection
    conn = create_connection()
    try:
        # Claim the highest-priority pending job
        row = conn.execute(
            "SELECT * FROM jobs WHERE status='pending' ORDER BY priority ASC, created_at ASC LIMIT 1"
        ).fetchone()
        if not row:
            return False
        job_id = row["id"]
        # Atomic claim
        updated = conn.execute(
            "UPDATE jobs SET status='running', worker_id=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
            "WHERE id=? AND status='pending'",
            (_WORKER_ID, job_id),
        ).rowcount
        conn.commit()
        if not updated:
            return False  # Another worker claimed it
    except Exception:
        conn.close()
        raise

    payload = json.loads(row["payload_json"] or "{}")
    job_type = row["type"]
    log.info("Running job %d type=%s", job_id, job_type)

    try:
        result = await _dispatch(job_type, payload)
        conn.execute(
            "UPDATE jobs SET status='done', result_json=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
            (json.dumps(result), job_id),
        )
        conn.commit()
        log.info("Job %d done", job_id)
    except Exception as exc:
        log.exception("Job %d failed: %s", job_id, exc)
        conn.execute(
            "UPDATE jobs SET status='failed', error_msg=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
            (str(exc), job_id),
        )
        conn.commit()
    finally:
        conn.close()
    return True


async def _dispatch(job_type: str, payload: dict) -> dict:
    loop = asyncio.get_event_loop()

    if job_type == "ingest_csv":
        return await loop.run_in_executor(None, _handle_ingest, payload)

    if job_type == "run_ml":
        return await loop.run_in_executor(None, _handle_ml, payload)

    if job_type == "simulation_c":
        return await loop.run_in_executor(None, _handle_sim_c, payload)

    if job_type == "export":
        return await loop.run_in_executor(None, _handle_export, payload)

    if job_type == "reconstruct_track":
        return await loop.run_in_executor(None, _handle_reconstruct, payload)

    raise ValueError(f"Unknown job type: {job_type}")


def _handle_ingest(payload: dict) -> dict:
    from backend.database import create_connection
    from backend.services.ingestion import ingest_csv, ingest_csv_files
    conn = create_connection()
    try:
        # Support both legacy single file_path and new multi-file file_paths
        file_paths = payload.get("file_paths") or [payload["file_path"]]
        if len(file_paths) == 1:
            result = ingest_csv(payload["session_id"], file_paths[0], conn)
        else:
            result = ingest_csv_files(payload["session_id"], file_paths, conn)
        conn.commit()
        return result
    finally:
        conn.close()


def _handle_ml(payload: dict) -> dict:
    from backend.database import create_connection
    from backend.analysis.ml.clustering import run_ml_training
    conn = create_connection()
    try:
        result = run_ml_training(conn)
        conn.commit()
        return result
    finally:
        conn.close()


def _handle_sim_c(payload: dict) -> dict:
    from backend.database import create_connection
    from backend.analysis.simulation import simulate_mode_c
    import json as _json
    conn = create_connection()
    try:
        lap_id = payload.get("lap_id")
        tel = conn.execute("SELECT * FROM lap_telemetry WHERE lap_id=?", (lap_id,)).fetchone()
        if not tel:
            raise ValueError(f"No telemetry for lap {lap_id}")
        import numpy as np
        from backend.analysis.lap_analyzer import LapData
        from backend.analysis.alltrax_settings import AlltraxSettings
        from backend.analysis.gear_ratio import GearRatioConfig
        from backend.analysis.vehicle_config import VehicleConfig
        time_arr  = np.array(_json.loads(tel["time_json"]))
        speed_arr = np.array(_json.loads(tel["speed_json"]))
        lap = LapData(lap_number=0, start_idx=0, end_idx=len(time_arr)-1,
                      lap_time=float(time_arr[-1]-time_arr[0]),
                      time=time_arr, speed=speed_arr)
        import backend.config as cfg
        max_c = min(payload.get("max_current", 180), cfg.MAX_CURRENT_HARD_LIMIT)
        settings = AlltraxSettings(max_current=max_c, accel_rate=payload.get("accel_rate", 64))
        gear = GearRatioConfig(gear_ratio=payload.get("gear_ratio", 5.0))
        vehicle = VehicleConfig(kart_mass_kg=payload.get("mass_kg", 115.0))
        result = simulate_mode_c(
            lap=lap, settings=settings, gear=gear, vehicle=vehicle,
            tyre_psi_rear=payload.get("tyre_psi_rear", 10.0),
            tyre_psi_front=payload.get("tyre_psi_front", 10.0),
            motor_temp_c=payload.get("motor_temp_c", 25.0),
            weight_lap_time=payload.get("weight_speed", 0.5),
            weight_energy=payload.get("weight_energy", 0.5),
        )
        # Persist
        sess_row = conn.execute("SELECT session_id FROM laps WHERE id=?", (lap_id,)).fetchone()
        session_id = sess_row["session_id"] if sess_row else None
        conn.execute(
            "INSERT INTO simulation_results(session_id, lap_id, mode, goal, weight_speed, weight_energy, "
            "lap_time_s, energy_kwh, delta_json, inputs_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (session_id, lap_id, "C", payload.get("goal", "lap_time"),
             payload.get("weight_speed", 0.5), payload.get("weight_energy", 0.5),
             result.lap_time_s, result.energy_kwh,
             _json.dumps(result.delta_array.tolist() if hasattr(result, "delta_array") else []),
             _json.dumps(payload)),
        )
        return {"lap_time_s": result.lap_time_s, "energy_kwh": result.energy_kwh}
    finally:
        conn.close()


def _handle_export(payload: dict) -> dict:
    from backend.database import create_connection
    from backend.services.export_service import export_session
    conn = create_connection()
    try:
        result = export_session(payload["session_id"], conn)
        conn.commit()
        return result
    finally:
        conn.close()


def _handle_reconstruct(payload: dict) -> dict:
    from backend.database import create_connection
    from backend.services.ingestion import _rebuild_track_map
    conn = create_connection()
    try:
        _rebuild_track_map(payload["track_id"], payload["lap_id"], conn)
        conn.commit()
        return {"track_id": payload["track_id"], "rebuilt": True}
    finally:
        conn.close()
