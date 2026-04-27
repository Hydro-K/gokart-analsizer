"""Driver CRUD + style + benchmarks + evolution."""
from __future__ import annotations
import sqlite3
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import DriverCreate, DriverUpdate, DriverOut, DriverStyleOut, BenchmarkOut

router = APIRouter(tags=["drivers"])


class SessionEvolutionPoint(BaseModel):
    session_id: int
    date: str
    session_type: str
    track_name: str
    lap_count: int
    best_lap_s: Optional[float]
    avg_lap_s: Optional[float]
    std_dev_s: Optional[float]
    cv_pct: Optional[float]         # coefficient of variation %
    avg_smoothness: Optional[float]
    avg_throttle_var: Optional[float]


def _row_to_driver(row: sqlite3.Row) -> DriverOut:
    d = dict(row)
    return DriverOut(
        id=d["id"], name=d["name"], notes=d["notes"],
        settings_json=d.get("settings_json") or "{}",
        created_at=d["created_at"],
    )


@router.get("", response_model=List[DriverOut])
def list_drivers(db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    return [_row_to_driver(r) for r in db.execute("SELECT * FROM drivers ORDER BY name").fetchall()]


@router.post("", response_model=DriverOut, status_code=201)
def create_driver(body: DriverCreate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    cur = db.execute("INSERT INTO drivers(name, notes) VALUES(?,?)", (body.name, body.notes))
    row = db.execute("SELECT * FROM drivers WHERE id=?", (cur.lastrowid,)).fetchone()
    return _row_to_driver(row)


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(driver_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM drivers WHERE id=?", (driver_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Driver not found")
    return _row_to_driver(row)


@router.put("/{driver_id}", response_model=DriverOut)
def update_driver(driver_id: int, body: DriverUpdate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM drivers WHERE id=?", (driver_id,)).fetchone():
        raise HTTPException(404, "Driver not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        db.execute(f"UPDATE drivers SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?",
                   (*updates.values(), driver_id))
    return _row_to_driver(db.execute("SELECT * FROM drivers WHERE id=?", (driver_id,)).fetchone())


@router.delete("/{driver_id}", status_code=204)
def delete_driver(driver_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM drivers WHERE id=?", (driver_id,)).fetchone():
        raise HTTPException(404, "Driver not found")
    if db.execute("SELECT id FROM sessions WHERE driver_id=? LIMIT 1", (driver_id,)).fetchone():
        raise HTTPException(400, "Cannot delete driver with existing sessions")
    db.execute("DELETE FROM drivers WHERE id=?", (driver_id,))


@router.get("/{driver_id}/style", response_model=DriverStyleOut)
def get_driver_style(driver_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM driver_styles WHERE driver_id=?", (driver_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No style data yet — upload sessions and run ML training")
    return DriverStyleOut(**dict(row))


@router.get("/{driver_id}/benchmarks", response_model=List[BenchmarkOut])
def get_driver_benchmarks(driver_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute("SELECT * FROM benchmarks WHERE driver_id=?", (driver_id,)).fetchall()
    return [BenchmarkOut(**dict(r)) for r in rows]


@router.get("/{driver_id}/evolution", response_model=List[SessionEvolutionPoint])
def get_driver_evolution(driver_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    if not db.execute("SELECT id FROM drivers WHERE id=?", (driver_id,)).fetchone():
        raise HTTPException(404, "Driver not found")

    sessions = db.execute(
        """SELECT s.id, s.date, s.session_type,
                  t.name AS track_name
           FROM sessions s
           JOIN tracks t ON t.id = s.track_id
           WHERE s.driver_id=?
           ORDER BY s.date, s.id""",
        (driver_id,),
    ).fetchall()

    result: List[SessionEvolutionPoint] = []
    for sess in sessions:
        sid = sess["id"]
        laps = db.execute(
            "SELECT lap_time_s FROM laps WHERE session_id=? AND is_valid=1",
            (sid,),
        ).fetchall()
        lap_times = [r["lap_time_s"] for r in laps]

        best_lap = min(lap_times) if lap_times else None
        avg_lap  = float(np.mean(lap_times)) if lap_times else None
        std_dev  = float(np.std(lap_times, ddof=0)) if len(lap_times) > 1 else 0.0 if lap_times else None
        cv_pct   = float(std_dev / avg_lap * 100) if (avg_lap and std_dev is not None and avg_lap > 0) else None

        # Aggregate feature vectors for this session (join through laps)
        fv_rows = db.execute(
            """SELECT fv.smoothness_score, fv.throttle_variance
               FROM feature_vectors fv
               JOIN laps l ON l.id = fv.lap_id
               WHERE l.session_id=?""",
            (sid,),
        ).fetchall()
        avg_smooth = float(np.mean([r["smoothness_score"] for r in fv_rows])) if fv_rows else None
        avg_tv     = float(np.mean([r["throttle_variance"] for r in fv_rows])) if fv_rows else None

        result.append(SessionEvolutionPoint(
            session_id=sid,
            date=sess["date"],
            session_type=sess["session_type"],
            track_name=sess["track_name"],
            lap_count=len(lap_times),
            best_lap_s=round(best_lap, 3) if best_lap else None,
            avg_lap_s=round(avg_lap, 3) if avg_lap else None,
            std_dev_s=round(std_dev, 3) if std_dev is not None else None,
            cv_pct=round(cv_pct, 2) if cv_pct is not None else None,
            avg_smoothness=round(avg_smooth, 1) if avg_smooth else None,
            avg_throttle_var=round(avg_tv, 4) if avg_tv else None,
        ))
    return result
