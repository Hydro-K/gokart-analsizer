"""Strat-OS configuration. Reads from environment variables with sane defaults."""
from __future__ import annotations
import os
from pathlib import Path

# ── Base paths ────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = Path(os.getenv("STRATOS_DATA_DIR", BASE_DIR / "data"))
DB_PATH    = DATA_DIR / "strat-os.db"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
MODEL_DIR  = DATA_DIR / "models"
ARCHIVE_DIR= DATA_DIR / "archive"

# ── Runtime mode ──────────────────────────────────────────────────────────────
PI_MODE    = os.getenv("STRATOS_PI_MODE", "false").lower() == "true"
DEBUG      = os.getenv("STRATOS_DEBUG", "false").lower() == "true"

# ── Auth ──────────────────────────────────────────────────────────────────────
TOKEN_EXPIRE_HOURS = int(os.getenv("STRATOS_TOKEN_EXPIRE_HOURS", "720"))  # 30 days
SECRET_SALT        = os.getenv("STRATOS_SECRET_SALT", "strat-os-change-me")

# ── Storage thresholds (%) ────────────────────────────────────────────────────
STORAGE_WARN_PCT      = int(os.getenv("STRATOS_STORAGE_WARN", "70"))
STORAGE_CRITICAL_PCT  = int(os.getenv("STRATOS_STORAGE_CRITICAL", "80"))
STORAGE_EMERGENCY_PCT = int(os.getenv("STRATOS_STORAGE_EMERGENCY", "90"))

# ── Archive backend ───────────────────────────────────────────────────────────
# "local" | "smb" | "rclone_gdrive" | "disabled"
ARCHIVE_BACKEND  = os.getenv("STRATOS_ARCHIVE_BACKEND", "disabled")
SMB_SHARE_PATH   = os.getenv("STRATOS_SMB_SHARE", "")
RCLONE_REMOTE    = os.getenv("STRATOS_RCLONE_REMOTE", "gdrive:strat-os-archive")

# ── Job queue ─────────────────────────────────────────────────────────────────
JOB_POLL_INTERVAL = float(os.getenv("STRATOS_JOB_POLL", "0.5"))

# ── EVGP hard limit — never settable via env ──────────────────────────────────
MAX_CURRENT_HARD_LIMIT = 220  # Amps — EVGP rule, never exceed

def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR, MODEL_DIR, ARCHIVE_DIR):
        d.mkdir(parents=True, exist_ok=True)
