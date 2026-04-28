"""Track CRUD + map endpoint + reconstruct."""
from __future__ import annotations
import json
import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import TrackCreate, TrackUpdate, TrackOut, TrackMapOut

router = APIRouter(tags=["tracks"])


def _row_to_track(row) -> TrackOut:
    return TrackOut(
        id=row["id"],
        name=row["name"],
        lat_center=row["lat_center"],
        lon_center=row["lon_center"],
        length_m=row["length_m"],
        has_map=row["local_xy"] is not None,
        created_at=row["created_at"],
    )


@router.get("", response_model=List[TrackOut])
def list_tracks(db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    return [_row_to_track(r) for r in db.execute("SELECT * FROM tracks ORDER BY name").fetchall()]


@router.post("", response_model=TrackOut, status_code=201)
def create_track(body: TrackCreate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    cur = db.execute(
        "INSERT INTO tracks(name, lat_center, lon_center) VALUES(?,?,?)",
        (body.name, body.lat_center, body.lon_center),
    )
    return _row_to_track(db.execute("SELECT * FROM tracks WHERE id=?", (cur.lastrowid,)).fetchone())


@router.get("/{track_id}", response_model=TrackOut)
def get_track(track_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Track not found")
    return _row_to_track(row)


@router.put("/{track_id}", response_model=TrackOut)
def update_track(track_id: int, body: TrackUpdate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM tracks WHERE id=?", (track_id,)).fetchone():
        raise HTTPException(404, "Track not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        db.execute(f"UPDATE tracks SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?",
                   (*updates.values(), track_id))
    return _row_to_track(db.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone())


@router.delete("/{track_id}", status_code=204)
def delete_track(track_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM tracks WHERE id=?", (track_id,)).fetchone():
        raise HTTPException(404, "Track not found")
    if db.execute("SELECT id FROM sessions WHERE track_id=? LIMIT 1", (track_id,)).fetchone():
        raise HTTPException(400, "Cannot delete track with existing sessions")
    db.execute("DELETE FROM tracks WHERE id=?", (track_id,))


@router.get("/{track_id}/map", response_model=TrackMapOut)
def get_map(track_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Track not found")
    if not row["local_xy"]:
        raise HTTPException(404, "No map yet — upload a session with GPS data first")
    xy = json.loads(row["local_xy"])
    return TrackMapOut(track_id=track_id, local_xy=xy, length_m=row["length_m"])


@router.post("/{track_id}/reconstruct")
def reconstruct_map(track_id: int,
                    db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    import numpy as np
    from backend.analysis.gps_reconstruction import reconstruct_track

    row = db.execute("SELECT id FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Track not found")

    gps_rows = db.execute(
        "SELECT t.lat_json, t.lon_json FROM lap_telemetry t "
        "JOIN laps l ON l.id=t.lap_id "
        "WHERE l.track_id=? AND t.lat_json IS NOT NULL AND l.is_valid=1 "
        "ORDER BY l.lap_time_s ASC",
        (track_id,),
    ).fetchall()
    if not gps_rows:
        raise HTTPException(400, "No GPS laps available for this track")

    all_lat, all_lon = [], []
    for r in gps_rows:
        all_lat.extend(json.loads(r["lat_json"]))
        all_lon.extend(json.loads(r["lon_json"]))

    try:
        track_map = reconstruct_track(np.array(all_lat), np.array(all_lon))
    except Exception as exc:
        raise HTTPException(400, f"Reconstruction failed: {exc}")

    db.execute(
        "UPDATE tracks SET local_xy=?, lat_center=?, lon_center=?, length_m=? WHERE id=?",
        (json.dumps(track_map.local_xy), track_map.lat_center, track_map.lon_center,
         track_map.length_m, track_id),
    )
    return {"message": "Track map rebuilt", "length_m": track_map.length_m, "points": len(track_map.local_xy)}
