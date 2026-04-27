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
    """Ingest a single AiM CSV file."""
    from backend.analysis.data_loader import load_aim_csv

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {file_path}")
    raw = load_aim_csv(str(path))
    if raw.warnings:
        log.warning("CSV warnings for session %d: %s", session_id, raw.warnings)
    return _ingest_raw(session_id, raw, db)


def _ingest_raw(session_id: int, raw, db: sqlite3.Connection) -> dict:
    """Core ingestion pipeline given a parsed RawSessionData object."""
    from backend.analysis.lap_analyzer import analyse_session

    # 1. Detect laps
    session_analysis = analyse_session(
        raw.time, raw.speed, raw.lat, raw.lon, raw.beacon, raw.has_beacon
    )
    if not session_analysis.laps:
        raise ValueError("No laps detected in the uploaded file(s). "
                         "Check that the CSV contains speed data and at least one full lap.")

    sess_row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    driver_id = sess_row["driver_id"]
    kart_id   = sess_row["kart_id"]
    track_id  = sess_row["track_id"]

    lap_ids = []
    # 2. Persist laps + telemetry
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
        lat_list   = [float(v) for v in lap.lat]   if hasattr(lap, "lat")   and lap.lat   is not None and len(lap.lat)   > 0 else None
        lon_list   = [float(v) for v in lap.lon]   if hasattr(lap, "lon")   and lap.lon   is not None and len(lap.lon)   > 0 else None
        phase_list = list(lap.phase)                if hasattr(lap, "phase") and lap.phase is not None and len(lap.phase) > 0 else None

        def _slice_channel(raw_arr, start_idx: int, end_idx: int):
            if raw_arr is None:
                return None
            try:
                sl = raw_arr[start_idx:end_idx + 1]
                return [float(v) for v in sl] if len(sl) > 0 else None
            except Exception:
                return None

        si, ei = lap.start_idx, lap.end_idx
        lat_acc_list  = _slice_channel(getattr(raw, "lateral_acc",  None), si, ei)
        inl_acc_list  = _slice_channel(getattr(raw, "inline_acc",   None), si, ei)
        yaw_list      = _slice_channel(getattr(raw, "yaw_rate",     None), si, ei)
        roll_list     = _slice_channel(getattr(raw, "roll_rate",    None), si, ei)
        pitch_list    = _slice_channel(getattr(raw, "pitch_rate",   None), si, ei)
        vert_acc_list = _slice_channel(getattr(raw, "vertical_acc", None), si, ei)
        batt_v_list   = _slice_channel(getattr(raw, "battery_v",   None), si, ei)

        db.execute(
            "INSERT INTO lap_telemetry(lap_id, time_json, speed_json, lat_json, lon_json, phase_json,"
            " lateral_acc_json, inline_acc_json, yaw_rate_json, roll_rate_json,"
            " pitch_rate_json, vertical_acc_json, battery_v_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lap_id,
             json.dumps(time_list),
             json.dumps(speed_list),
             json.dumps(lat_list)      if lat_list      else None,
             json.dumps(lon_list)      if lon_list      else None,
             json.dumps(phase_list)    if phase_list    else None,
             json.dumps(lat_acc_list)  if lat_acc_list  else None,
             json.dumps(inl_acc_list)  if inl_acc_list  else None,
             json.dumps(yaw_list)      if yaw_list      else None,
             json.dumps(roll_list)     if roll_list     else None,
             json.dumps(pitch_list)    if pitch_list    else None,
             json.dumps(vert_acc_list) if vert_acc_list else None,
             json.dumps(batt_v_list)   if batt_v_list   else None),
        )

    # 3. Extract ML features
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

    # 4. GPS track reconstruction if we have GPS data
    has_gps = any(
        db.execute("SELECT lat_json FROM lap_telemetry WHERE lap_id=?", (lid,)).fetchone()["lat_json"]
        for lid in lap_ids
    )
    if has_gps:
        track_map_row = db.execute("SELECT local_xy FROM tracks WHERE id=?", (track_id,)).fetchone()
        if track_map_row and not track_map_row["local_xy"]:
            _rebuild_track_map_multi(track_id, session_id, db)

    # 5. Update benchmarks
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


def _stitch_raw_sessions(raws: list) -> "RawSessionData":
    """Concatenate multiple RawSessionData objects in chronological order.

    AiM files from the same session have relative timestamps starting near 0.
    This offsets each file's time so they chain end-to-end before merging.
    """
    from backend.analysis.data_loader import RawSessionData

    if len(raws) == 1:
        return raws[0]

    # Detect absolute vs relative timestamps
    # Relative: all files start near 0 (< 60s); absolute: large epoch values
    all_relative = all(r.time[0] < 60 for r in raws if len(r.time) > 0)

    if all_relative:
        # Sort by filename so session_001.csv < session_002.csv etc.
        raws = sorted(raws, key=lambda r: r.filename)
    else:
        # Absolute timestamps — sort by first sample value
        raws = sorted(raws, key=lambda r: r.time[0] if len(r.time) > 0 else 0)

    time_out, speed_out, lat_out, lon_out, beacon_out = [], [], [], [], []
    all_warnings: list = []
    offset = 0.0

    for i, raw in enumerate(raws):
        t = raw.time.copy()
        if all_relative:
            t = t + offset
            # Next file offset = end of this file + small gap to separate sessions
            offset = float(t[-1]) + 0.2 if len(t) else offset

        time_out.append(t)
        speed_out.append(raw.speed)
        lat_out.append(raw.lat)
        lon_out.append(raw.lon)
        beacon_out.append(raw.beacon)
        all_warnings.extend(raw.warnings)

    return RawSessionData(
        time=np.concatenate(time_out),
        speed=np.concatenate(speed_out),
        lat=np.concatenate(lat_out),
        lon=np.concatenate(lon_out),
        beacon=np.concatenate(beacon_out),
        has_gps=any(r.has_gps for r in raws),
        has_beacon=any(r.has_beacon for r in raws),
        filename=" + ".join(r.filename for r in raws),
        sample_rate=raws[0].sample_rate,
        warnings=all_warnings,
    )


def ingest_csv_files(session_id: int, file_paths: list, db: sqlite3.Connection,
                     relative_paths: Optional[list] = None) -> dict:
    """Ingest multiple CSV files.

    If relative_paths contains folder prefixes (e.g. 'a_0001_CSV/_GPS.csv'),
    files are grouped by their top-level folder and each group is loaded as an
    AiM session folder, then all groups are stitched chronologically into one
    session — supporting upload of multiple AiM session runs at once.
    """
    from backend.analysis.data_loader import load_aim_csv, load_aim_folder
    import tempfile, shutil as _shutil

    rel = relative_paths or []

    aim_keywords = {"gps", "laps", "lateralacc", "inlineacc", "yawrate",
                    "rollrate", "pitchrate", "verticalacc", "battery"}

    def _is_aim_group(paths: list) -> bool:
        names = [Path(fp).stem.lower().replace(" ", "").replace("_", "") for fp in paths]
        return sum(1 for n in names if any(kw in n for kw in aim_keywords)) >= 3

    def _load_group_as_aim(paths: list, folder_label: str):
        """Copy files to a temp dir (restoring original names) and load as AiM folder."""
        tmp = Path(tempfile.mkdtemp(prefix="stratos_aim_"))
        try:
            for fp in paths:
                orig = Path(fp).name
                # Strip uuid_ prefix to restore the original AiM filename
                parts = orig.split("_", 1)
                dest_name = parts[1] if len(parts) == 2 and len(parts[0]) == 32 else orig
                _shutil.copy2(fp, tmp / dest_name)
            raw = load_aim_folder(str(tmp))
            raw.warnings.append(f"Loaded AiM folder '{folder_label}' ({len(paths)} files)")
            return raw
        finally:
            _shutil.rmtree(tmp, ignore_errors=True)

    # Group files by source folder using relative paths
    folder_groups: dict[str, list] = {}
    has_folders = False
    for i, fp in enumerate(file_paths):
        rel_path = (rel[i] if i < len(rel) else "").replace("\\", "/")
        parts = rel_path.split("/")
        folder = parts[0] if len(parts) > 1 else ""
        if folder:
            has_folders = True
        folder_groups.setdefault(folder, []).append(fp)

    if has_folders and len(folder_groups) > 1:
        # Multiple source folders — load each as an AiM folder then stitch together
        raws = []
        for folder_name in sorted(folder_groups.keys()):
            paths = folder_groups[folder_name]
            if _is_aim_group(paths):
                raw = _load_group_as_aim(paths, folder_name)
            else:
                raw = load_aim_csv(str(paths[0]))
            raws.append(raw)
        log.info("Multi-folder ingest: %d folders → session %d", len(raws), session_id)
        stitched = _stitch_raw_sessions(raws)
        return _ingest_raw(session_id, stitched, db)

    # Single folder or no folder info
    all_paths = file_paths
    if _is_aim_group(all_paths):
        folder_label = (sorted(folder_groups.keys())[0] if folder_groups else "") or "upload"
        raw = _load_group_as_aim(all_paths, folder_label)
        return _ingest_raw(session_id, raw, db)

    # Plain CSV files — stitch in order
    raws = []
    for fp in all_paths:
        if not Path(fp).exists():
            raise FileNotFoundError(f"CSV not found: {fp}")
        raws.append(load_aim_csv(str(fp)))
    if not raws:
        raise ValueError("No files to ingest")
    stitched = _stitch_raw_sessions(raws)
    if len(raws) > 1:
        log.info("Stitched %d files → session %d", len(raws), session_id)
    return _ingest_raw(session_id, stitched, db)


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


def _rebuild_track_map_multi(track_id: int, session_id: int, db: sqlite3.Connection) -> None:
    """Build a GPS track map averaged across all valid GPS laps in a session."""
    try:
        from backend.analysis.gps_reconstruction import reconstruct_track_multi_lap
        rows = db.execute(
            "SELECT t.lat_json, t.lon_json, l.lap_time_s FROM lap_telemetry t "
            "JOIN laps l ON l.id=t.lap_id "
            "WHERE l.session_id=? AND l.is_valid=1 AND t.lat_json IS NOT NULL "
            "ORDER BY l.lap_time_s ASC",
            (session_id,),
        ).fetchall()
        if not rows:
            return
        # Use up to 5 best laps for averaging (best laps = cleanest GPS lines)
        lap_gps = []
        for row in rows[:5]:
            lat = np.array(json.loads(row["lat_json"]))
            lon = np.array(json.loads(row["lon_json"]))
            if len(lat) >= 20:
                lap_gps.append((lat, lon))
        if not lap_gps:
            return
        track_map = reconstruct_track_multi_lap(lap_gps)
        db.execute(
            "UPDATE tracks SET local_xy=?, lat_center=?, lon_center=?, length_m=? WHERE id=?",
            (json.dumps(track_map.local_xy),
             track_map.lat_center, track_map.lon_center,
             track_map.length_m, track_id),
        )
        log.info("Track map built from %d laps (session %d)", len(lap_gps), session_id)
    except Exception as e:
        log.warning("Multi-lap track reconstruction failed: %s", e)


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
