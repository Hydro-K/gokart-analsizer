"""Kart maintenance log router."""
from __future__ import annotations
import sqlite3
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer

router = APIRouter(tags=["maintenance"])


class MaintenanceLogCreate(BaseModel):
    type: str
    description: str = ""
    date: str
    laps_at_service: int = 0
    next_due_laps: Optional[int] = None


class MaintenanceLogOut(MaintenanceLogCreate):
    id: int
    kart_id: int
    created_at: str


@router.get("/karts/{kart_id}/maintenance", response_model=List[MaintenanceLogOut])
def list_maintenance(kart_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    if not db.execute("SELECT id FROM karts WHERE id=?", (kart_id,)).fetchone():
        raise HTTPException(404, "Kart not found")
    rows = db.execute(
        "SELECT * FROM maintenance_logs WHERE kart_id=? ORDER BY date DESC, id DESC",
        (kart_id,),
    ).fetchall()
    return [MaintenanceLogOut(**dict(r)) for r in rows]


@router.post("/karts/{kart_id}/maintenance", response_model=MaintenanceLogOut, status_code=201)
def add_maintenance(kart_id: int, body: MaintenanceLogCreate,
                    db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM karts WHERE id=?", (kart_id,)).fetchone():
        raise HTTPException(404, "Kart not found")
    cur = db.execute(
        "INSERT INTO maintenance_logs(kart_id, type, description, date, laps_at_service, next_due_laps) VALUES(?,?,?,?,?,?)",
        (kart_id, body.type, body.description, body.date, body.laps_at_service, body.next_due_laps),
    )
    row = db.execute("SELECT * FROM maintenance_logs WHERE id=?", (cur.lastrowid,)).fetchone()
    return MaintenanceLogOut(**dict(row))


@router.delete("/karts/{kart_id}/maintenance/{log_id}", status_code=204)
def delete_maintenance(kart_id: int, log_id: int,
                       db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    db.execute("DELETE FROM maintenance_logs WHERE id=? AND kart_id=?", (log_id, kart_id))
