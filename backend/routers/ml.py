"""ML training trigger and driver style endpoints."""
from __future__ import annotations
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import DriverStyleOut, MLStatusOut

router = APIRouter(tags=["ml"])


@router.post("/train")
def trigger_training(db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    count = db.execute("SELECT COUNT(*) FROM feature_vectors").fetchone()[0]
    if count < 5:
        raise HTTPException(400, f"Need at least 5 laps with features (have {count}). Upload more sessions first.")
    cur = db.execute(
        "INSERT INTO jobs(type, priority, payload_json) VALUES(?,?,?)",
        ("run_ml", 4, json.dumps({"triggered_by": "manual"})),
    )
    return {"job_id": cur.lastrowid, "message": f"ML training queued ({count} laps available)"}


@router.get("/driver/{driver_id}/style", response_model=DriverStyleOut)
def driver_style(driver_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM driver_styles WHERE driver_id=?", (driver_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No style data yet — upload sessions and run ML training")
    return DriverStyleOut(**dict(row))


@router.get("/status", response_model=MLStatusOut)
def ml_status(db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    from backend.analysis.ml.model_store import model_exists, last_trained
    count = db.execute("SELECT COUNT(*) FROM feature_vectors").fetchone()[0]
    return MLStatusOut(
        model_exists=model_exists(),
        n_training_samples=count,
        last_trained=last_trained(),
    )
