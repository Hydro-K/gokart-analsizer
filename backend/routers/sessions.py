"""Session CRUD, CSV upload, post-session readings, compliance, recommendations."""
from __future__ import annotations
import json
import sqlite3
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import (
    SessionCreate, SessionUpdate, SessionOut,
    PostSessionCreate, PostSessionOut,
    ComplianceReportOut, ComplianceItemOut, RecommendationOut,
)
import backend.config as cfg

router = APIRouter(tags=["sessions"])


def _row_to_session(row, db: sqlite3.Connection) -> SessionOut:
    laps = db.execute(
        "SELECT COUNT(*) as c, MIN(lap_time_s) as best FROM laps WHERE session_id=? AND is_valid=1",
        (row["id"],),
    ).fetchone()
    d = db.execute("SELECT name FROM drivers WHERE id=?", (row["driver_id"],)).fetchone()
    k = db.execute("SELECT name FROM karts WHERE id=?",   (row["kart_id"],)).fetchone()
    t = db.execute("SELECT name FROM tracks WHERE id=?",  (row["track_id"],)).fetchone()
    return SessionOut(
        id=row["id"],
        driver_id=row["driver_id"],
        kart_id=row["kart_id"],
        track_id=row["track_id"],
        driver_name=d["name"] if d else "Unknown",
        kart_name=k["name"] if k else "Unknown",
        track_name=t["name"] if t else "Unknown",
        date=row["date"],
        session_type=row["session_type"],
        notes=row["notes"],
        lap_count=laps["c"],
        best_lap_s=laps["best"],
        created_at=row["created_at"],
    )


@router.get("", response_model=List[SessionOut])
def list_sessions(
    driver_id: Optional[int] = None,
    kart_id: Optional[int] = None,
    track_id: Optional[int] = None,
    db: sqlite3.Connection = Depends(get_db),
    _=Depends(get_current_user),
):
    q = "SELECT * FROM sessions WHERE 1=1"
    params: list = []
    if driver_id:
        q += " AND driver_id=?"; params.append(driver_id)
    if kart_id:
        q += " AND kart_id=?"; params.append(kart_id)
    if track_id:
        q += " AND track_id=?"; params.append(track_id)
    q += " ORDER BY date DESC, created_at DESC"
    rows = db.execute(q, params).fetchall()
    return [_row_to_session(r, db) for r in rows]


@router.post("/upload", status_code=202)
def upload_session(
    file: UploadFile = File(...),
    driver_id: int = Form(...),
    kart_id: int = Form(...),
    track_id: int = Form(...),
    date: str = Form(...),
    session_type: str = Form("Practice 1"),
    notes: str = Form(""),
    db: sqlite3.Connection = Depends(get_db),
    _=Depends(require_engineer),
):
    # Validate FK existence
    for table, fk_id, label in [("drivers", driver_id, "Driver"), ("karts", kart_id, "Kart"), ("tracks", track_id, "Track")]:
        if not db.execute(f"SELECT id FROM {table} WHERE id=?", (fk_id,)).fetchone():
            raise HTTPException(400, f"{label} ID {fk_id} not found. Create it first.")

    # Save uploaded file
    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'session.csv').name}"
    dest = cfg.UPLOAD_DIR / safe_name
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create session record
    cur = db.execute(
        "INSERT INTO sessions(driver_id, kart_id, track_id, date, session_type, raw_file_path, notes) "
        "VALUES(?,?,?,?,?,?,?)",
        (driver_id, kart_id, track_id, date, session_type, str(dest), notes),
    )
    session_id = cur.lastrowid

    # Queue ingestion job
    job_cur = db.execute(
        "INSERT INTO jobs(type, priority, payload_json) VALUES(?,?,?)",
        ("ingest_csv", 1, json.dumps({"session_id": session_id, "file_path": str(dest)})),
    )
    return {"session_id": session_id, "job_id": job_cur.lastrowid, "message": "Upload received, processing queued"}


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    return _row_to_session(row, db)


@router.put("/{session_id}", response_model=SessionOut)
def update_session(session_id: int, body: SessionUpdate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone():
        raise HTTPException(404, "Session not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        db.execute(f"UPDATE sessions SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?",
                   (*updates.values(), session_id))
    return _row_to_session(db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone(), db)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    row = db.execute("SELECT raw_file_path FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    if row["raw_file_path"]:
        p = Path(row["raw_file_path"])
        if p.exists():
            p.unlink(missing_ok=True)
    db.execute("DELETE FROM sessions WHERE id=?", (session_id,))


@router.get("/{session_id}/laps")
def get_session_laps(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    if not db.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone():
        raise HTTPException(404, "Session not found")
    rows = db.execute("SELECT * FROM laps WHERE session_id=? ORDER BY lap_number", (session_id,)).fetchall()
    return [dict(r) for r in rows]


@router.get("/{session_id}/post-session-reading", response_model=PostSessionOut)
def get_post_session(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM post_session_readings WHERE session_id=?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No post-session reading yet")
    return PostSessionOut(**dict(row))


@router.post("/{session_id}/post-session-reading", response_model=PostSessionOut, status_code=201)
def upsert_post_session(session_id: int, body: PostSessionCreate,
                        db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone():
        raise HTTPException(404, "Session not found")
    data = body.model_dump()
    existing = db.execute("SELECT id FROM post_session_readings WHERE session_id=?", (session_id,)).fetchone()
    if existing:
        sets = ", ".join(f"{k}=?" for k in data)
        db.execute(f"UPDATE post_session_readings SET {sets} WHERE session_id=?",
                   (*data.values(), session_id))
    else:
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        db.execute(f"INSERT INTO post_session_readings(session_id, {cols}) VALUES(?,{placeholders})",
                   (session_id, *data.values()))
    return PostSessionOut(**dict(db.execute("SELECT * FROM post_session_readings WHERE session_id=?", (session_id,)).fetchone()))


@router.get("/{session_id}/compliance", response_model=ComplianceReportOut)
def session_compliance(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    from backend.analysis.competition_rules import CompetitionRules, ComplianceChecker
    from backend.analysis.alltrax_settings import AlltraxSettings
    from backend.analysis.gear_ratio import GearRatioConfig
    import json as _json

    sess = db.execute("SELECT kart_id FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not sess:
        raise HTTPException(404, "Session not found")
    kart = db.execute("SELECT settings_json, gear_json FROM karts WHERE id=?", (sess["kart_id"],)).fetchone()
    rules_row = db.execute("SELECT * FROM competition_rules WHERE id=1").fetchone()
    rules = CompetitionRules.from_dict(dict(rules_row)) if rules_row else CompetitionRules()

    try:
        settings = AlltraxSettings(**_json.loads(kart["settings_json"] or "{}"))
    except Exception:
        settings = AlltraxSettings()
    try:
        gear = GearRatioConfig(**_json.loads(kart["gear_json"] or "{}"))
    except Exception:
        gear = GearRatioConfig()

    checker = ComplianceChecker(rules)
    report = checker.check(settings, gear)
    items = [ComplianceItemOut(
        rule_name=i.rule_name, rule_section=i.rule_section,
        status=i.status, current_value=i.current_value,
        limit_value=i.limit_value, message=i.message,
        actionable=i.actionable,
    ) for i in report.items]
    return ComplianceReportOut(passed=report.passed, items=items)


@router.get("/{session_id}/recommendations", response_model=List[RecommendationOut])
def session_recommendations(session_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    from backend.analysis.recommendations import RecommendationEngine
    from backend.analysis.alltrax_settings import AlltraxSettings
    from backend.analysis.gear_ratio import GearRatioConfig
    from backend.analysis.lap_analyzer import SessionAnalysis, LapData
    import json as _json

    sess = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not sess:
        raise HTTPException(404, "Session not found")
    kart = db.execute("SELECT * FROM karts WHERE id=?", (sess["kart_id"],)).fetchone()

    lap_rows = db.execute(
        "SELECT l.*, t.time_json, t.speed_json, t.phase_json FROM laps l "
        "LEFT JOIN lap_telemetry t ON t.lap_id=l.id "
        "WHERE l.session_id=? AND l.is_valid=1 ORDER BY l.lap_number",
        (session_id,),
    ).fetchall()
    if not lap_rows:
        return []

    laps = []
    for lr in lap_rows:
        try:
            t = _json.loads(lr["time_json"] or "[]")
            s = _json.loads(lr["speed_json"] or "[]")
            p = _json.loads(lr["phase_json"] or "[]")
            import numpy as np
            ld = LapData(
                lap_number=lr["lap_number"],
                start_idx=0, end_idx=max(0, len(t)-1),
                lap_time=lr["lap_time_s"],
                time=np.array(t, dtype=float),
                speed=np.array(s, dtype=float),
                phase=np.array(p),
            )
            laps.append(ld)
        except Exception:
            continue

    if not laps:
        return []

    times = [l.lap_time for l in laps]
    best_idx = int(np.argmin(times))
    avg = float(np.mean(times))
    std = float(np.std(times))
    consistency = max(0.0, 100.0 - (std / avg * 100)) if avg > 0 else 100.0
    session_analysis = SessionAnalysis(laps=laps, best_lap_index=best_idx,
                                       avg_lap_time=avg, std_lap_time=std,
                                       consistency_pct=consistency)
    try:
        settings = AlltraxSettings(**_json.loads(kart["settings_json"] or "{}"))
    except Exception:
        settings = AlltraxSettings()
    try:
        gear = GearRatioConfig(**_json.loads(kart["gear_json"] or "{}"))
    except Exception:
        gear = GearRatioConfig()

    engine = RecommendationEngine()
    recs = engine.generate(session_analysis, settings, gear)
    return [RecommendationOut(
        category=r.category,
        setting_key=r.setting_key,
        current_value=r.current_value,
        recommended_value=r.recommended_value,
        delta=r.delta,
        reason=r.reason,
        predicted_outcome=getattr(r, "predicted_outcome", r.reason),
        priority=r.priority,
    ) for r in recs]
