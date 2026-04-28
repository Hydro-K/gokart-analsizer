"""Lap telemetry, corners, sectors, energy, smoothness, comparison."""
from __future__ import annotations
import json
import sqlite3
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.schemas import LapOut, LapTelemetryOut, CornerOut, SectorOut, CompareRequest, CompareOut, DeltaPoint
from backend.routers.auth import require_engineer

router = APIRouter(tags=["laps"])


def _get_lap_or_404(lap_id: int, db: sqlite3.Connection):
    row = db.execute("SELECT * FROM laps WHERE id=?", (lap_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Lap not found")
    return row


def _lttb_downsample(x: list, y: list, threshold: int):
    """Largest-Triangle-Three-Buckets downsampling."""
    n = len(x)
    if n <= threshold:
        return x, y
    x_arr, y_arr = np.array(x), np.array(y)
    bucket_size = (n - 2) / (threshold - 2)
    sampled_x, sampled_y = [x_arr[0]], [y_arr[0]]
    a = 0
    for i in range(threshold - 2):
        avg_start = int(np.floor((i + 1) * bucket_size) + 1)
        avg_end   = int(np.floor((i + 2) * bucket_size) + 1)
        avg_x = float(np.mean(x_arr[avg_start:avg_end]))
        avg_y = float(np.mean(y_arr[avg_start:avg_end]))
        rng_start = int(np.floor(i * bucket_size) + 1)
        rng_end   = int(np.floor((i + 1) * bucket_size) + 1)
        max_area = -1.0
        next_a = rng_start
        for j in range(rng_start, rng_end):
            area = abs((x_arr[a] - avg_x) * (y_arr[j] - y_arr[a]) -
                       (x_arr[a] - x_arr[j]) * (avg_y - y_arr[a])) * 0.5
            if area > max_area:
                max_area = area
                next_a = j
        sampled_x.append(float(x_arr[next_a]))
        sampled_y.append(float(y_arr[next_a]))
        a = next_a
    sampled_x.append(float(x_arr[-1]))
    sampled_y.append(float(y_arr[-1]))
    return sampled_x, sampled_y


@router.get("/{lap_id}", response_model=LapOut)
def get_lap(lap_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = _get_lap_or_404(lap_id, db)
    return LapOut(**{**dict(row), 'is_valid': bool(row["is_valid"])})


@router.get("/{lap_id}/telemetry", response_model=LapTelemetryOut)
def get_telemetry(
    lap_id: int,
    points: Optional[int] = Query(None, ge=50, le=5000),
    db: sqlite3.Connection = Depends(get_db),
    _=Depends(get_current_user),
):
    _get_lap_or_404(lap_id, db)
    row = db.execute("SELECT * FROM lap_telemetry WHERE lap_id=?", (lap_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No telemetry data for this lap")
    time_data  = json.loads(row["time_json"])
    speed_data = json.loads(row["speed_json"])
    lat_data   = json.loads(row["lat_json"])  if row["lat_json"]   else None
    lon_data   = json.loads(row["lon_json"])  if row["lon_json"]   else None
    phase_data = json.loads(row["phase_json"]) if row["phase_json"] else None

    if points and len(time_data) > points:
        orig_time = time_data  # keep for lat/lon/phase downsampling (must match original length)
        time_data, speed_data = _lttb_downsample(orig_time, speed_data, points)
        if lat_data:  _, lat_data  = _lttb_downsample(orig_time, lat_data,  points)
        if lon_data:  _, lon_data  = _lttb_downsample(orig_time, lon_data,  points)
        if phase_data:
            idxs = np.round(np.linspace(0, len(phase_data)-1, points)).astype(int).tolist()
            phase_data = [phase_data[i] for i in idxs]

    return LapTelemetryOut(
        lap_id=lap_id,
        time=time_data,
        speed_ms=speed_data,
        lat=lat_data,
        lon=lon_data,
        phase=phase_data,
        has_gps=lat_data is not None,
    )


@router.get("/{lap_id}/corners", response_model=List[CornerOut])
def get_corners(lap_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    _get_lap_or_404(lap_id, db)
    row = db.execute("SELECT * FROM lap_telemetry WHERE lap_id=?", (lap_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No telemetry data")
    from backend.analysis.corner_detector import detect_corners
    time_arr  = np.array(json.loads(row["time_json"]))
    speed_arr = np.array(json.loads(row["speed_json"]))
    corners = detect_corners(time_arr, speed_arr)
    return [CornerOut(
        corner_index=i+1,
        entry_speed_kmh=round(c.entry_speed * 3.6, 1),
        apex_speed_kmh=round(c.apex_speed * 3.6, 1),
        exit_speed_kmh=round(c.exit_speed * 3.6, 1),
        entry_time_s=round(float(time_arr[c.entry_idx]), 3),
        apex_time_s=round(float(time_arr[c.apex_idx]), 3),
    ) for i, c in enumerate(corners)]


@router.get("/{lap_id}/sectors", response_model=List[SectorOut])
def get_sectors(
    lap_id: int,
    n: int = Query(5, ge=2, le=20),
    db: sqlite3.Connection = Depends(get_db),
    _=Depends(get_current_user),
):
    _get_lap_or_404(lap_id, db)
    row = db.execute("SELECT * FROM lap_telemetry WHERE lap_id=?", (lap_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No telemetry data")
    from backend.analysis.deep_analysis import sector_splits, speed_vs_distance
    from backend.analysis.lap_analyzer import LapData
    time_arr  = np.array(json.loads(row["time_json"]))
    speed_arr = np.array(json.loads(row["speed_json"]))
    lap = LapData(lap_number=0, start_idx=0, end_idx=len(time_arr)-1,
                  lap_time=float(time_arr[-1]-time_arr[0]) if len(time_arr) > 1 else 0,
                  time=time_arr, speed=speed_arr)
    sectors = sector_splits(lap, n_sectors=n)
    return [SectorOut(
        sector_num=s.sector_num,
        dist_start_m=round(s.dist_start_m, 1),
        dist_end_m=round(s.dist_end_m, 1),
        time_s=round(s.time_s, 3),
        avg_speed_kmh=round(s.avg_speed_kmh, 1),
        min_speed_kmh=round(s.min_speed_kmh, 1),
        max_speed_kmh=round(s.max_speed_kmh, 1),
    ) for s in sectors]


@router.get("/{lap_id}/energy")
def get_energy(lap_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    _get_lap_or_404(lap_id, db)
    row = db.execute("SELECT * FROM lap_telemetry WHERE lap_id=?", (lap_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No telemetry data")
    from backend.analysis.deep_analysis import estimate_energy
    time_arr  = np.array(json.loads(row["time_json"]))
    speed_arr = np.array(json.loads(row["speed_json"]))
    result = estimate_energy(time_arr, speed_arr)
    return {"lap_id": lap_id, **result.__dict__}


@router.get("/{lap_id}/smoothness")
def get_smoothness(lap_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    _get_lap_or_404(lap_id, db)
    row = db.execute("SELECT * FROM lap_telemetry WHERE lap_id=?", (lap_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No telemetry data")
    from backend.analysis.deep_analysis import driver_smoothness_score
    time_arr  = np.array(json.loads(row["time_json"]))
    speed_arr = np.array(json.loads(row["speed_json"]))
    score = driver_smoothness_score(time_arr, speed_arr)
    return {"lap_id": lap_id, "smoothness_score": round(score, 1)}


@router.get("/{lap_id}/features")
def get_features(lap_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM feature_vectors WHERE lap_id=?", (lap_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Features not computed yet")
    return dict(row)


@router.patch("/{lap_id}/notes")
def update_lap_notes(lap_id: int, payload: dict, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    _get_lap_or_404(lap_id, db)
    db.execute("UPDATE laps SET notes=? WHERE id=?", (payload.get("notes", ""), lap_id))
    return {"ok": True}


@router.patch("/{lap_id}/valid")
def set_lap_valid(lap_id: int, payload: dict, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    _get_lap_or_404(lap_id, db)
    db.execute("UPDATE laps SET is_valid=? WHERE id=?", (1 if payload.get("is_valid") else 0, lap_id))
    return {"ok": True}


@router.post("/compare", response_model=CompareOut)
def compare_laps(body: CompareRequest, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    if len(body.lap_ids) != 2:
        raise HTTPException(400, "Exactly 2 lap IDs required")
    a_id, b_id = body.lap_ids
    a_tel = db.execute("SELECT * FROM lap_telemetry WHERE lap_id=?", (a_id,)).fetchone()
    b_tel = db.execute("SELECT * FROM lap_telemetry WHERE lap_id=?", (b_id,)).fetchone()
    a_lap = db.execute("SELECT lap_time_s FROM laps WHERE id=?", (a_id,)).fetchone()
    b_lap = db.execute("SELECT lap_time_s FROM laps WHERE id=?", (b_id,)).fetchone()
    if not all([a_tel, b_tel, a_lap, b_lap]):
        raise HTTPException(404, "One or both laps not found")
    from backend.analysis.deep_analysis import time_delta_vs_distance
    from backend.analysis.lap_analyzer import LapData
    def _mk_lap(row):
        t = np.array(json.loads(row["time_json"]), dtype=float)
        s = np.array(json.loads(row["speed_json"]), dtype=float)
        return LapData(lap_number=0, start_idx=0, end_idx=max(0, len(t)-1),
                       lap_time=float(t[-1]-t[0]) if len(t) > 1 else 0,
                       time=t, speed=s)
    lap_a, lap_b = _mk_lap(a_tel), _mk_lap(b_tel)
    dist_arr, delta_arr = time_delta_vs_distance(lap_a, lap_b, n_points=500)
    pts = [DeltaPoint(distance_m=round(float(d), 1), delta_s=round(float(v), 4))
           for d, v in zip(dist_arr, delta_arr)]
    return CompareOut(
        lap_a_id=a_id, lap_b_id=b_id,
        delta_points=pts,
        lap_a_time_s=a_lap["lap_time_s"],
        lap_b_time_s=b_lap["lap_time_s"],
    )
