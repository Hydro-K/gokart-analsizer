"""Driver CRUD + style + benchmarks."""
from __future__ import annotations
import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import DriverCreate, DriverUpdate, DriverOut, DriverStyleOut, BenchmarkOut

router = APIRouter(tags=["drivers"])


def _row_to_driver(row: sqlite3.Row) -> DriverOut:
    return DriverOut(id=row["id"], name=row["name"], notes=row["notes"], created_at=row["created_at"])


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
