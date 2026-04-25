"""Storage stats, archive management, and cleanup."""
from __future__ import annotations
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import StorageStatsOut

router = APIRouter(tags=["storage"])


@router.get("/stats", response_model=StorageStatsOut)
def storage_stats(db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    from backend.services.storage_manager import get_storage_stats
    return get_storage_stats(db)


@router.post("/archive/{session_id}")
def archive_session(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    from backend.services.storage_manager import archive_session_raw
    if not db.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone():
        raise HTTPException(404, "Session not found")
    result = archive_session_raw(session_id, db)
    return result


@router.post("/cleanup")
def run_cleanup(db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    from backend.services.storage_manager import run_auto_cleanup
    return run_auto_cleanup(db)


@router.get("/tiers")
def list_tiers(_=Depends(get_current_user)):
    import backend.config as cfg
    tiers = [{"name": "sd", "path": str(cfg.DATA_DIR), "description": "Primary SD card storage"}]
    if cfg.ARCHIVE_BACKEND == "smb" and cfg.SMB_SHARE_PATH:
        tiers.append({"name": "smb", "path": cfg.SMB_SHARE_PATH, "description": "Network SMB share"})
    elif cfg.ARCHIVE_BACKEND == "rclone_gdrive":
        tiers.append({"name": "gdrive", "path": cfg.RCLONE_REMOTE, "description": "Google Drive via rclone"})
    return tiers
