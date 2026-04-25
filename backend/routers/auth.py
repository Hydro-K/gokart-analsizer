"""Authentication routes: login, logout, current user, user management."""
from __future__ import annotations
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
import sqlite3

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Request

from backend.database import get_db
from backend.schemas import LoginRequest, TokenOut, UserOut, UserCreate, UserUpdate
import backend.config as cfg

router = APIRouter(tags=["auth"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _row_to_user(row: sqlite3.Row) -> UserOut:
    return UserOut(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        role=row["role"],
        created_at=row["created_at"],
    )


def _get_token_user(token: str, db: sqlite3.Connection) -> Optional[UserOut]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = db.execute(
        "SELECT u.* FROM users u JOIN auth_tokens t ON t.user_id=u.id "
        "WHERE t.token=? AND t.expires_at > ?",
        (token, now),
    ).fetchone()
    return _row_to_user(row) if row else None


def _token_expiry() -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=cfg.TOKEN_EXPIRE_HOURS)
    return exp.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_current_user(request: Request, db: sqlite3.Connection = Depends(get_db)) -> UserOut:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        token = request.cookies.get("stratos_token", "")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = _get_token_user(token, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


def require_admin(user: UserOut = Depends(get_current_user)) -> UserOut:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


def require_engineer(user: UserOut = Depends(get_current_user)) -> UserOut:
    if user.role not in ("admin", "engineer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer or admin only")
    return user


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
    if not row or not _check_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO auth_tokens(token, user_id, expires_at) VALUES (?,?,?)",
        (token, row["id"], _token_expiry()),
    )
    return TokenOut(token=token, user=_row_to_user(row))


@router.post("/logout")
def logout(request: Request, db: sqlite3.Connection = Depends(get_db)):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    db.execute("DELETE FROM auth_tokens WHERE token=?", (token,))
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserOut)
def me(user: UserOut = Depends(get_current_user)):
    return user


@router.post("/register", response_model=TokenOut)
def register_first_admin(body: UserCreate, db: sqlite3.Connection = Depends(get_db)):
    """Create the first admin user. Only allowed when no users exist (first-boot wizard)."""
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        raise HTTPException(status_code=403, detail="Registration disabled — admin already exists")
    pw_hash = _hash_password(body.password)
    cur = db.execute(
        "INSERT INTO users(username, display_name, role, password_hash) VALUES(?,?,?,?)",
        (body.username, body.display_name, "admin", pw_hash),
    )
    user_id = cur.lastrowid
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO auth_tokens(token, user_id, expires_at) VALUES(?,?,?)",
        (token, user_id, _token_expiry()),
    )
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return TokenOut(token=token, user=_row_to_user(row))
