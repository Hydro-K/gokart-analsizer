"""Kart CRUD + setup history."""
from __future__ import annotations
import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import KartCreate, KartUpdate, KartOut, SetupCreate, SetupOut

router = APIRouter(tags=["karts"])


def _row_to_kart(row) -> KartOut:
    return KartOut(**{k: row[k] for k in KartOut.model_fields})


@router.get("", response_model=List[KartOut])
def list_karts(db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    return [_row_to_kart(r) for r in db.execute("SELECT * FROM karts ORDER BY name").fetchall()]


@router.post("", response_model=KartOut, status_code=201)
def create_kart(body: KartCreate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    cur = db.execute(
        "INSERT INTO karts(name, motor_type, battery_type, mass_kg, settings_json, gear_json, notes) "
        "VALUES(?,?,?,?,?,?,?)",
        (body.name, body.motor_type, body.battery_type, body.mass_kg,
         body.settings_json, body.gear_json, body.notes),
    )
    return _row_to_kart(db.execute("SELECT * FROM karts WHERE id=?", (cur.lastrowid,)).fetchone())


@router.get("/{kart_id}", response_model=KartOut)
def get_kart(kart_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM karts WHERE id=?", (kart_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Kart not found")
    return _row_to_kart(row)


@router.put("/{kart_id}", response_model=KartOut)
def update_kart(kart_id: int, body: KartUpdate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM karts WHERE id=?", (kart_id,)).fetchone():
        raise HTTPException(404, "Kart not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        db.execute(f"UPDATE karts SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?",
                   (*updates.values(), kart_id))
    return _row_to_kart(db.execute("SELECT * FROM karts WHERE id=?", (kart_id,)).fetchone())


@router.delete("/{kart_id}", status_code=204)
def delete_kart(kart_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM karts WHERE id=?", (kart_id,)).fetchone():
        raise HTTPException(404, "Kart not found")
    if db.execute("SELECT id FROM sessions WHERE kart_id=? LIMIT 1", (kart_id,)).fetchone():
        raise HTTPException(400, "Cannot delete kart with existing sessions")
    db.execute("DELETE FROM karts WHERE id=?", (kart_id,))


@router.get("/{kart_id}/setups", response_model=List[SetupOut])
def list_setups(kart_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute("SELECT * FROM kart_setups WHERE kart_id=? ORDER BY created_at DESC", (kart_id,)).fetchall()
    return [SetupOut(**dict(r)) for r in rows]


@router.post("/{kart_id}/setups", response_model=SetupOut, status_code=201)
def create_setup(kart_id: int, body: SetupCreate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    cur = db.execute(
        "INSERT INTO kart_setups(kart_id, settings_json, gear_json, notes) VALUES(?,?,?,?)",
        (kart_id, body.settings_json, body.gear_json, body.notes),
    )
    return SetupOut(**dict(db.execute("SELECT * FROM kart_setups WHERE id=?", (cur.lastrowid,)).fetchone()))


@router.get("/{kart_id}/setups/active", response_model=SetupOut)
def active_setup(kart_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute(
        "SELECT * FROM kart_setups WHERE kart_id=? ORDER BY created_at DESC LIMIT 1", (kart_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "No setup saved for this kart")
    return SetupOut(**dict(row))
