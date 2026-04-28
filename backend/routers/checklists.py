"""Pre-session checklist templates and runs."""
from __future__ import annotations
import json
import sqlite3
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.database import get_db
from backend.routers.auth import get_current_user, require_engineer

router = APIRouter(tags=["checklists"])


class ChecklistTemplateCreate(BaseModel):
    kart_id: Optional[int] = None
    name: str
    items: List[str]


class ChecklistTemplateOut(BaseModel):
    id: int
    kart_id: Optional[int]
    name: str
    items: List[str]
    created_at: str


class ChecklistRunCreate(BaseModel):
    template_id: int
    session_id: Optional[int] = None
    checked: List[str]


class ChecklistRunOut(BaseModel):
    id: int
    template_id: int
    session_id: Optional[int]
    checked: List[str]
    completed_at: Optional[str]
    created_at: str


def _tmpl_out(row) -> ChecklistTemplateOut:
    d = dict(row)
    return ChecklistTemplateOut(
        id=d["id"], kart_id=d["kart_id"], name=d["name"],
        items=json.loads(d["items_json"] or "[]"),
        created_at=d["created_at"],
    )


def _run_out(row) -> ChecklistRunOut:
    d = dict(row)
    return ChecklistRunOut(
        id=d["id"], template_id=d["template_id"], session_id=d["session_id"],
        checked=json.loads(d["checked_json"] or "[]"),
        completed_at=d.get("completed_at"),
        created_at=d["created_at"],
    )


@router.get("/templates", response_model=List[ChecklistTemplateOut])
def list_templates(kart_id: Optional[int] = None, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    if kart_id:
        rows = db.execute("SELECT * FROM checklist_templates WHERE kart_id=? OR kart_id IS NULL ORDER BY name", (kart_id,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM checklist_templates ORDER BY name").fetchall()
    return [_tmpl_out(r) for r in rows]


@router.post("/templates", response_model=ChecklistTemplateOut, status_code=201)
def create_template(body: ChecklistTemplateCreate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    cur = db.execute(
        "INSERT INTO checklist_templates(kart_id, name, items_json) VALUES(?,?,?)",
        (body.kart_id, body.name, json.dumps(body.items)),
    )
    return _tmpl_out(db.execute("SELECT * FROM checklist_templates WHERE id=?", (cur.lastrowid,)).fetchone())


@router.put("/templates/{tmpl_id}", response_model=ChecklistTemplateOut)
def update_template(tmpl_id: int, body: ChecklistTemplateCreate,
                    db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    if not db.execute("SELECT id FROM checklist_templates WHERE id=?", (tmpl_id,)).fetchone():
        raise HTTPException(404, "Template not found")
    db.execute("UPDATE checklist_templates SET kart_id=?, name=?, items_json=? WHERE id=?",
               (body.kart_id, body.name, json.dumps(body.items), tmpl_id))
    return _tmpl_out(db.execute("SELECT * FROM checklist_templates WHERE id=?", (tmpl_id,)).fetchone())


@router.delete("/templates/{tmpl_id}", status_code=204)
def delete_template(tmpl_id: int, db: sqlite3.Connection = Depends(get_db), _=Depends(require_engineer)):
    db.execute("DELETE FROM checklist_templates WHERE id=?", (tmpl_id,))


@router.post("/runs", response_model=ChecklistRunOut, status_code=201)
def create_run(body: ChecklistRunCreate, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    import datetime as _dt
    completed_at = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ") if len(body.checked) > 0 else None
    cur = db.execute(
        "INSERT INTO checklist_runs(template_id, session_id, checked_json, completed_at) VALUES(?,?,?,?)",
        (body.template_id, body.session_id, json.dumps(body.checked), completed_at),
    )
    return _run_out(db.execute("SELECT * FROM checklist_runs WHERE id=?", (cur.lastrowid,)).fetchone())


@router.get("/runs", response_model=List[ChecklistRunOut])
def list_runs(session_id: Optional[int] = None, db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    if session_id:
        rows = db.execute("SELECT * FROM checklist_runs WHERE session_id=? ORDER BY created_at DESC", (session_id,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM checklist_runs ORDER BY created_at DESC LIMIT 50").fetchall()
    return [_run_out(r) for r in rows]
