"""CSV ingestion pipeline: file → analysis → SQLite."""
from __future__ import annotations
import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


def ingest_csv(session_id: int, file_path: str, db: sqlite3.Connection) -> dict:
    """Full ingestion pipeline for an AiM CSV file.

    Steps:
    1. Parse CSV (data_loader)
    2. Detect laps (lap_analyzer)
    3. Persist laps + lap_telemetry
    4. Extract ML feature vectors
    5. Reconstruct GPS track if new data
    6. Update benchmarks
    """
    from backend.analysis.data_loader import load_aim_csv
    from backend.analysis.lap_analyzer import analyse_session

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {file_path}")

    # 1. Parse
    raw = load_aim_csv(str(path))
    if raw.warnings:
        log.warning("CSV warnings for session %d: %s", session_id, raw.warnings)

    # 2. Analyse
    session_analysis = analyse_session(raw)
    if not session_analysis.laps:
        raise ValueError("No laps detected in the file")

    # Fetch session metadata
    sess_row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    driver_id = sess_row["driver_id"]
    kart_id   = sess_row["kart_id"]
    track_id  = sess_row["track_id"]

    lap_ids = []
    # 3. Persist laps
    for lap in session_analysis.laps:
        cur = db.execute(
            "INSERT INTO laps(session_id, driver_id, kart_id, track_id, lap_number, lap_time_s, is_valid) "
            "VALUES(?,?,?,?,?,?,?)",
            (session_id, driver_id, kart_id, track_id,
             lap.lap_number, float(lap.lap_time), 1),
        )
        lap_id = cur.lastrowid
        lap_ids.append(lap_id)

        time_list  = [float(t) for t in lap.time]
        speed_list = [float(s) for s in lap.speed]
        lat_list   = [float(v) for v in lap.lat]  if hasattr(lap, "lat")  and lap.lat  is not None and len(lap.lat)  > 0 else None
        lon_list   = [float(v) for v in lap.lon]  if hasattr(lap, "lon")  and lap.lon  is not None and len(lap.lon)  > 0 else None
        phase_list = list(lap.phase)               if hasattr(lap, "phase") and lap.phase is not None and len(lap.phase) > 0 else None

        db.execute(
            "INSERT INTO lap_telemetry(lap_id, time_json, speed_json, lat_json, lon_json, phase_json) "
            "VALUES(?,?,?,?,?,?)",
            (lap_id,
             json.dumps(time_list),
             json.dumps(speed_list),
             json.dumps(lat_list)   if lat_list   else None,
             json.dumps(lon_list)   if lon_list   else None,
             json.dumps(phase_list) if phase_list else None),
        )

    # 4. Extract ML features
    for i, lap in enumerate(session_analysis.laps):
        try:
            from backend.analysis.ml.feature_extractor import extract_features
            features = extract_features(lap)
            db.execute(
                "INSERT OR REPLACE INTO feature_vectors"
                "(lap_id, driver_id, throttle_variance, braking_intensity, "
                "corner_entry_speed_avg, accel_consistency, smoothness_score) "
                "VALUES(?,?,?,?,?,?,?)",
                (lap_ids[i], driver_id,
                 features["throttle_variance"],
                 features["braking_intensity"],
                 features["corner_entry_speed_avg"],
                 features["accel_consistency"],
                 features["smoothness_score"]),
            )
        except Exception as e:
            log.warning("Feature extraction failed for lap %d: %s", lap_ids[i], e)

    # 5. GPS track reconstruction if we have GPS data
    has_gps = any(
        db.execute("SELECT lat_json FROM lap_telemetry WHERE lap_id=?", (lid,)).fetchone()["lat_json"]
        for lid in lap_ids
    )
    if has_gps:
        best_lap_row = db.execute(
            "SELECT l.id FROM laps l JOIN lap_telemetry t ON t.lap_id=l.id "
            "WHERE l.session_id=? AND t.lat_json IS NOT NULL AND l.is_valid=1 "
            "ORDER BY l.lap_time_s ASC LIMIT 1",
            (session_id,),
        ).fetchone()
        track_map_row = db.execute("SELECT local_xy FROM tracks WHERE id=?", (track_id,)).fetchone()
        if track_map_row and not track_map_row["local_xy"] and best_lap_row:
            _rebuild_track_map(track_id, best_lap_row["id"], db)

    # 6. Update benchmarks
    _update_benchmarks(session_id, driver_id, kart_id, track_id, db)

    # Auto-trigger ML if driver has enough features
    n_features = db.execute(
        "SELECT COUNT(*) FROM feature_vectors WHERE driver_id=?", (driver_id,)
    ).fetchone()[0]
    if n_features >= 5:
        db.execute(
            "INSERT INTO jobs(type, priority, payload_json) VALUES(?,?,?)",
            ("run_ml", 6, json.dumps({"triggered_by": "auto", "driver_id": driver_id})),
        )

    return {
        "session_id": session_id,
        "laps_ingested": len(lap_ids),
        "has_gps": has_gps,
        "warnings": raw.warnings,
    }


def _rebuild_track_map(track_id: int, lap_id: int, db: sqlite3.Connection) -> None:
    try:
        from backend.analysis.gps_reconstruction import reconstruct_track
        tel = db.execute("SELECT lat_json, lon_json FROM lap_telemetry WHERE lap_id=?", (lap_id,)).fetchone()
        if not tel or not tel["lat_json"]:
            return
        lat = np.array(json.loads(tel["lat_json"]))
        lon = np.array(json.loads(tel["lon_json"]))
        if len(lat) < 20:
            return
        track_map = reconstruct_track(lat, lon)
        db.execute(
            "UPDATE tracks SET local_xy=?, lat_center=?, lon_center=?, length_m=? WHERE id=?",
            (json.dumps(track_map.local_xy),
             track_map.lat_center, track_map.lon_center,
             track_map.length_m, track_id),
        )
    except Exception as e:
        log.warning("Track reconstruction failed: %s", e)


def _update_benchmarks(session_id: int, driver_id: int, kart_id: int, track_id: int,
                        db: sqlite3.Connection) -> None:
    try:
        from backend.analysis.deep_analysis import sector_splits
        from backend.analysis.lap_analyzer import LapData
        lap_rows = db.execute(
            "SELECT l.id, l.lap_time_s, t.time_json, t.speed_json FROM laps l "
            "JOIN lap_telemetry t ON t.lap_id=l.id "
            "WHERE l.session_id=? AND l.is_valid=1 ORDER BY l.lap_time_s",
            (session_id,),
        ).fetchall()
        if not lap_rows:
            return
        session_best = lap_rows[0]["lap_time_s"]

        # Build LapData list for theoretical best calculation
        laps_obj = []
        for lr in lap_rows:
            try:
                t = np.array(json.loads(lr["time_json"]))
                s = np.array(json.loads(lr["speed_json"]))
                laps_obj.append(LapData(lap_number=0, start_idx=0, end_idx=len(t)-1,
                                        lap_time=lr["lap_time_s"], time=t, speed=s))
            except Exception:
                continue

        # Theoretical best: sum of best sector time across all laps (inline, n=5 sectors)
        theo_best = session_best
        if len(laps_obj) >= 2:
            try:
                N_SECTORS = 5
                all_sectors = []
                for lap in laps_obj:
                    segs = sector_splits(lap, N_SECTORS)
                    if len(segs) == N_SECTORS:
                        all_sectors.append(segs)
                if all_sectors:
                    theo_best = sum(
                        min(all_sectors[l][s].time_s for l in range(len(all_sectors)))
                        for s in range(N_SECTORS)
                    )
            except Exception:
                theo_best = session_best

        # Best ever for this driver+kart+track
        prev = db.execute(
            "SELECT best_ever_s FROM benchmarks WHERE track_id=? AND driver_id=? AND kart_id=?",
            (track_id, driver_id, kart_id),
        ).fetchone()
        best_ever = min(session_best, prev["best_ever_s"]) if prev and prev["best_ever_s"] else session_best

        db.execute(
            "INSERT INTO benchmarks(track_id, driver_id, kart_id, best_ever_s, best_session_s, theoretical_best_s) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(track_id,driver_id,kart_id) "
            "DO UPDATE SET best_ever_s=MIN(best_ever_s,excluded.best_ever_s), "
            "best_session_s=excluded.best_session_s, "
            "theoretical_best_s=excluded.theoretical_best_s, "
            "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
            (track_id, driver_id, kart_id, best_ever, session_best, theo_best),
        )
    except Exception as e:
        log.warning("Benchmark update failed: %s", e)
