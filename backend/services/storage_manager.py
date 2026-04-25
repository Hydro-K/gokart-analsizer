"""Tiered storage management: SD card primary, SMB/GDrive archive."""
from __future__ import annotations
import logging
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional

import backend.config as cfg
from backend.schemas import StorageStatsOut

log = logging.getLogger(__name__)


def get_disk_usage_pct(path: Path) -> float:
    try:
        usage = shutil.disk_usage(str(path))
        return usage.used / usage.total * 100
    except Exception:
        return 0.0


def get_storage_stats(db: sqlite3.Connection) -> StorageStatsOut:
    usage = shutil.disk_usage(str(cfg.DATA_DIR))
    sd_total_gb = usage.total / 1e9
    sd_used_gb  = usage.used  / 1e9
    sd_pct      = usage.used  / usage.total * 100

    hdd_avail   = False
    hdd_total   = None
    hdd_used    = None
    if cfg.ARCHIVE_BACKEND == "smb" and cfg.SMB_SHARE_PATH:
        try:
            u = shutil.disk_usage(cfg.SMB_SHARE_PATH)
            hdd_avail = True
            hdd_total = u.total / 1e9
            hdd_used  = u.used  / 1e9
        except Exception:
            pass
    elif cfg.ARCHIVE_BACKEND == "local" and cfg.ARCHIVE_DIR.exists():
        try:
            u = shutil.disk_usage(str(cfg.ARCHIVE_DIR))
            hdd_avail = True
            hdd_total = u.total / 1e9
            hdd_used  = u.used  / 1e9
        except Exception:
            pass

    sessions_on_sd = db.execute(
        "SELECT COUNT(*) FROM sessions s WHERE NOT EXISTS "
        "(SELECT 1 FROM storage_archive a WHERE a.session_id=s.id AND a.tier!='sd')"
    ).fetchone()[0]
    sessions_archived = db.execute(
        "SELECT COUNT(DISTINCT session_id) FROM storage_archive WHERE tier!='sd'"
    ).fetchone()[0]

    if sd_pct >= cfg.STORAGE_EMERGENCY_PCT:
        status = "emergency"
    elif sd_pct >= cfg.STORAGE_CRITICAL_PCT:
        status = "critical"
    elif sd_pct >= cfg.STORAGE_WARN_PCT:
        status = "warn"
    else:
        status = "ok"

    return StorageStatsOut(
        sd_total_gb=round(sd_total_gb, 2),
        sd_used_gb=round(sd_used_gb, 2),
        sd_pct=round(sd_pct, 1),
        hdd_available=hdd_avail,
        hdd_total_gb=round(hdd_total, 2) if hdd_total else None,
        hdd_used_gb=round(hdd_used, 2) if hdd_used else None,
        threshold_warn=cfg.STORAGE_WARN_PCT,
        threshold_critical=cfg.STORAGE_CRITICAL_PCT,
        threshold_emergency=cfg.STORAGE_EMERGENCY_PCT,
        status=status,
        sessions_on_sd=sessions_on_sd,
        sessions_archived=sessions_archived,
    )


def archive_session_raw(session_id: int, db: sqlite3.Connection) -> dict:
    sess = db.execute("SELECT raw_file_path FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not sess or not sess["raw_file_path"]:
        return {"session_id": session_id, "action": "no_raw_file"}
    raw_path = Path(sess["raw_file_path"])
    if not raw_path.exists():
        return {"session_id": session_id, "action": "file_not_found"}

    dest_path: Optional[str] = None
    tier = "deleted"

    if cfg.ARCHIVE_BACKEND == "smb" and cfg.SMB_SHARE_PATH:
        try:
            dest = Path(cfg.SMB_SHARE_PATH) / raw_path.name
            shutil.copy2(str(raw_path), str(dest))
            dest_path = str(dest)
            tier = "smb"
        except Exception as e:
            log.warning("SMB archive failed: %s", e)
    elif cfg.ARCHIVE_BACKEND == "local":
        dest = cfg.ARCHIVE_DIR / raw_path.name
        shutil.copy2(str(raw_path), str(dest))
        dest_path = str(dest)
        tier = "hdd"
    elif cfg.ARCHIVE_BACKEND == "rclone_gdrive":
        _internet_available = _ping_check()
        if _internet_available:
            try:
                subprocess.run(
                    ["rclone", "copy", str(raw_path), cfg.RCLONE_REMOTE],
                    timeout=60, check=True, capture_output=True
                )
                dest_path = f"{cfg.RCLONE_REMOTE}/{raw_path.name}"
                tier = "gdrive"
            except Exception as e:
                log.warning("rclone archive failed: %s", e)

    if tier in ("smb", "hdd", "gdrive"):
        raw_path.unlink(missing_ok=True)

    db.execute(
        "INSERT INTO storage_archive(session_id, tier, archive_path) VALUES(?,?,?)",
        (session_id, tier, dest_path),
    )
    return {"session_id": session_id, "action": "archived", "tier": tier, "dest": dest_path}


def run_auto_cleanup(db: sqlite3.Connection) -> dict:
    pct = get_disk_usage_pct(cfg.DATA_DIR)
    actions = []
    if pct < cfg.STORAGE_WARN_PCT:
        return {"action": "none", "sd_pct": round(pct, 1)}
    if pct >= cfg.STORAGE_CRITICAL_PCT:
        # Archive oldest sessions (keep 2 most recent per driver)
        rows = db.execute(
            "SELECT s.id FROM sessions s "
            "WHERE NOT EXISTS(SELECT 1 FROM storage_archive a WHERE a.session_id=s.id) "
            "ORDER BY s.date ASC, s.created_at ASC LIMIT 10"
        ).fetchall()
        for r in rows:
            result = archive_session_raw(r["id"], db)
            actions.append(result)
            if get_disk_usage_pct(cfg.DATA_DIR) < cfg.STORAGE_CRITICAL_PCT:
                break
    if pct >= cfg.STORAGE_EMERGENCY_PCT:
        # Delete raw CSVs already archived
        archived = db.execute(
            "SELECT DISTINCT s.raw_file_path FROM sessions s "
            "JOIN storage_archive a ON a.session_id=s.id WHERE s.raw_file_path IS NOT NULL"
        ).fetchall()
        for r in archived:
            p = Path(r["raw_file_path"])
            if p.exists():
                p.unlink(missing_ok=True)
                actions.append({"action": "deleted_raw", "path": str(p)})
    return {"action": "cleanup_done", "sd_pct_before": round(pct, 1), "steps": actions}


def _ping_check() -> bool:
    try:
        subprocess.run(["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                       timeout=5, check=True, capture_output=True)
        return True
    except Exception:
        return False
