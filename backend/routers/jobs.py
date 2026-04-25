"""Job queue status and management."""
from __future__ import annotations
import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer
from backend.schemas import JobOut

router = APIRouter(tags=["jobs"])


def _row_to_job(row) -> JobOut:
    return JobOut(
        id=row["id"],
        type=row["type"],
        status=row["status"],
        priority=row["priority"],
        result_json=row["result_json"],
        error_msg=row["error_msg"],
        worker_id=row["worker_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=List[JobOut])
def list_jobs(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: sqlite3.Connection = Depends(get_db),
    _=Depends(get_current_user),
):
    q = "SELECT * FROM jobs WHERE 1=1"
    params: list = []
    if status:
        q += " AND status=?"; params.append(status)
    if type:
        q += " AND type=?"; params.append(type)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return [_row_to_job(r) for r in db.execute(q, params).fetchall()]


@router.get("/pending/count")
def pending_count(db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    count = db.execute("SELECT COUNT(*) FROM jobs WHERE status='pending'").fetchone()[0]
    return {"count": count}


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    return _row_to_job(row)


@router.delete("/{job_id}", status_code=204)
def cancel_job(job_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    if row["status"] not in ("pending",):
        raise HTTPException(400, f"Cannot cancel job with status '{row['status']}'")
    db.execute("UPDATE jobs SET status='cancelled' WHERE id=?", (job_id,))
