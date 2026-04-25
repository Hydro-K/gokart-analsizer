"""User management — admin only."""
from __future__ import annotations
import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.routers.auth import require_admin, _hash_password, _row_to_user
from backend.schemas import UserCreate, UserUpdate, UserOut

router = APIRouter(tags=["users"])


@router.get("", response_model=List[UserOut])
def list_users(db: sqlite3.Connection = Depends(get_db), _=Depends(require_admin)):
    return [_row_to_user(r) for r in db.execute("SELECT * FROM users ORDER BY created_at").fetchall()]


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_admin)):
    existing = db.execute("SELECT id FROM users WHERE username=?", (body.username,)).fetchone()
    if existing:
        raise HTTPException(400, "Username already taken")
    cur = db.execute(
        "INSERT INTO users(username, display_name, role, password_hash) VALUES(?,?,?,?)",
        (body.username, body.display_name, body.role, _hash_password(body.password)),
    )
    row = db.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return _row_to_user(row)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(require_admin)):
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return _row_to_user(row)


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_admin)):
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    updates = {}
    if body.display_name is not None:
        updates["display_name"] = body.display_name
    if body.role is not None:
        updates["role"] = body.role
    if body.password is not None:
        updates["password_hash"] = _hash_password(body.password)
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE users SET {set_clause} WHERE id=?", (*updates.values(), user_id))
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _row_to_user(row)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(require_admin)):
    if not db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone():
        raise HTTPException(404, "User not found")
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] <= 1:
        raise HTTPException(400, "Cannot delete the last admin user")
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
