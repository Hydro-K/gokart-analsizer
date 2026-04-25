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
def reconstruct_map(track_id: int, background_tasks: BackgroundTasks,
                    db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    row = db.execute("SELECT id FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Track not found")
    # Find best GPS lap for this track (most GPS points = highest quality)
    lap_row = db.execute(
        "SELECT l.id FROM laps l JOIN lap_telemetry t ON t.lap_id=l.id "
        "WHERE l.track_id=? AND t.lat_json IS NOT NULL AND l.is_valid=1 "
        "ORDER BY l.lap_time_s ASC LIMIT 1",
        (track_id,),
    ).fetchone()
    if not lap_row:
        raise HTTPException(400, "No GPS laps available for this track")
    cur = db.execute(
        "INSERT INTO jobs(type, priority, payload_json) VALUES(?,?,?)",
        ("reconstruct_track", 3, json.dumps({"track_id": track_id, "lap_id": lap_row["id"]})),
    )
    return {"job_id": cur.lastrowid, "message": "Track reconstruction queued"}
