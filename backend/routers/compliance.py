"""Compliance check and competition rules management."""
from __future__ import annotations
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.routers.auth import get_current_user, require_admin
from backend.schemas import ComplianceReportOut, ComplianceItemOut, CompetitionRulesUpdate

router = APIRouter(tags=["compliance"])


@router.get("/rules")
def get_rules(db: sqlite3.Connection = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute("SELECT * FROM competition_rules WHERE id=1").fetchone()
    return dict(row) if row else {}


@router.put("/rules")
def update_rules(body: CompetitionRulesUpdate, db: sqlite3.Connection = Depends(get_db), _=Depends(require_admin)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"detail": "Nothing to update"}
    updates["updated_at"] = "strftime('%Y-%m-%dT%H:%M:%SZ','now')"
    # Build safe update — filter out the sentinel value
    real_updates = {k: v for k, v in updates.items() if k != "updated_at"}
    set_parts = [f"{k}=?" for k in real_updates] + ["updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')"]
    db.execute(f"UPDATE competition_rules SET {', '.join(set_parts)} WHERE id=1",
               (*real_updates.values(),))
    row = db.execute("SELECT * FROM competition_rules WHERE id=1").fetchone()
    # Refresh singleton
    from backend.analysis.competition_rules import CompetitionRules, set_rules
    set_rules(CompetitionRules.from_dict(dict(row)))
    return dict(row)


@router.post("/check", response_model=ComplianceReportOut)
def check_compliance(
    kart_id: int,
    db: sqlite3.Connection = Depends(get_db),
    _=Depends(get_current_user),
):
    from backend.analysis.competition_rules import CompetitionRules, ComplianceChecker
    from backend.analysis.alltrax_settings import AlltraxSettings
    from backend.analysis.gear_ratio import GearRatioConfig

    kart = db.execute("SELECT * FROM karts WHERE id=?", (kart_id,)).fetchone()
    if not kart:
        raise HTTPException(404, "Kart not found")
    rules_row = db.execute("SELECT * FROM competition_rules WHERE id=1").fetchone()
    rules = CompetitionRules.from_dict(dict(rules_row)) if rules_row else CompetitionRules()
    try:
        settings = AlltraxSettings(**json.loads(kart["settings_json"] or "{}"))
    except Exception:
        settings = AlltraxSettings()
    try:
        gear = GearRatioConfig(**json.loads(kart["gear_json"] or "{}"))
    except Exception:
        gear = GearRatioConfig()
    checker = ComplianceChecker(rules)
    report = checker.check(settings, gear)
    items = [ComplianceItemOut(
        rule_name=i.rule_name, status=i.status,
        measured=i.measured, limit=i.limit,
        message=i.message, actionable=i.actionable,
    ) for i in report.items]
    return ComplianceReportOut(passed=report.passed, items=items)
