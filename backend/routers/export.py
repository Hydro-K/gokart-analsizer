"""Export routes: session report, PNG charts, Alltrax .aep download."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import ExportJobOut

router = APIRouter(tags=["export"])


@router.post("/session/{session_id}/report", response_model=ExportJobOut)
def export_session_report(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    if not db.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone():
        raise HTTPException(404, "Session not found")
    cur = db.execute(
        "INSERT INTO jobs(type, priority, payload_json) VALUES(?,?,?)",
        ("export", 5, json.dumps({"session_id": session_id})),
    )
    return ExportJobOut(job_id=cur.lastrowid, message="Export job queued")


@router.get("/session/{session_id}/download")
def download_export(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    import backend.config as cfg
    export_dir = cfg.EXPORT_DIR / str(session_id)
    zip_path = export_dir.with_suffix(".zip")
    if not zip_path.exists():
        raise HTTPException(404, "Export not ready — queue a report job first")
    return FileResponse(str(zip_path), media_type="application/zip",
                        filename=f"strat-os-session-{session_id}.zip")


@router.get("/alltrax/{kart_id}")
def download_alltrax_aep(kart_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    from backend.analysis.alltrax_importer import export_alltrax_aep
    from backend.analysis.alltrax_settings import AlltraxSettings
    import backend.config as cfg
    import tempfile, os

    kart = db.execute("SELECT * FROM karts WHERE id=?", (kart_id,)).fetchone()
    if not kart:
        raise HTTPException(404, "Kart not found")
    try:
        settings = AlltraxSettings(**json.loads(kart["settings_json"] or "{}"))
    except Exception:
        settings = AlltraxSettings()
    tmp = tempfile.NamedTemporaryFile(suffix=".aep", delete=False, dir=str(cfg.EXPORT_DIR))
    tmp.close()
    export_alltrax_aep(settings, tmp.name)
    return FileResponse(tmp.name, media_type="application/octet-stream",
                        filename=f"kart-{kart_id}-alltrax.aep")
