"""Strat-OS FastAPI application entry point."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # must be before any other matplotlib import

import asyncio
import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import backend.config as cfg
from backend.database import init_db, create_connection

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG if cfg.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    cfg.ensure_dirs()
    init_db()
    log.info("Database initialized at %s", cfg.DB_PATH)

    from backend.services.job_runner import run_forever
    runner_task = asyncio.create_task(run_forever())
    log.info("Job runner started")

    yield

    # Shutdown
    runner_task.cancel()
    try:
        await runner_task
    except asyncio.CancelledError:
        pass
    log.info("Strat-OS shutdown complete")


app = FastAPI(
    title="Strat-OS",
    version="1.0.0",
    description="EV Kart Race Engineering Platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from backend.routers import (
    auth, users, drivers, karts, tracks,
    sessions, laps, compliance, jobs,
    simulation, ml, storage, export, reports,
)

app.include_router(auth.router,        prefix="/api/auth",        tags=["auth"])
app.include_router(users.router,       prefix="/api/users",       tags=["users"])
app.include_router(drivers.router,     prefix="/api/drivers",     tags=["drivers"])
app.include_router(karts.router,       prefix="/api/karts",       tags=["karts"])
app.include_router(tracks.router,      prefix="/api/tracks",      tags=["tracks"])
app.include_router(sessions.router,    prefix="/api/sessions",    tags=["sessions"])
app.include_router(laps.router,        prefix="/api/laps",        tags=["laps"])
app.include_router(compliance.router,  prefix="/api/compliance",  tags=["compliance"])
app.include_router(jobs.router,        prefix="/api/jobs",        tags=["jobs"])
app.include_router(simulation.router,  prefix="/api/simulation",  tags=["simulation"])
app.include_router(ml.router,          prefix="/api/ml",          tags=["ml"])
app.include_router(storage.router,     prefix="/api/storage",     tags=["storage"])
app.include_router(export.router,      prefix="/api/export",      tags=["export"])
app.include_router(reports.router,     prefix="/api/reports",     tags=["reports"])


@app.get("/api/benchmarks")
def all_benchmarks(_: Request):
    """All-time best laps per driver+kart+track combination."""
    from backend.routers.auth import get_current_user
    db = create_connection()
    try:
        rows = db.execute(
            "SELECT b.*, d.name as driver_name, k.name as kart_name, t.name as track_name "
            "FROM benchmarks b "
            "LEFT JOIN drivers d ON d.id=b.driver_id "
            "LEFT JOIN karts k ON k.id=b.kart_id "
            "LEFT JOIN tracks t ON t.id=b.track_id "
            "ORDER BY b.best_ever_s ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


@app.get("/api/system/status")
def system_status():
    """Health check + first-boot detection. No auth required."""
    db = create_connection()
    try:
        user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        session_count = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        driver_count = db.execute("SELECT COUNT(*) FROM drivers").fetchone()[0]
        pending_jobs = db.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='pending'"
        ).fetchone()[0]
    finally:
        db.close()

    import shutil
    disk = shutil.disk_usage(str(cfg.DATA_DIR))
    disk_pct = round(disk.used / disk.total * 100, 1)

    return {
        "status": "ok",
        "first_boot": user_count == 0,
        "version": _get_version(),
        "pi_mode": cfg.PI_MODE,
        "stats": {
            "users": user_count,
            "sessions": session_count,
            "drivers": driver_count,
            "pending_jobs": pending_jobs,
        },
        "storage": {
            "used_pct": disk_pct,
            "status": _disk_status(disk_pct),
        },
    }


def _disk_status(pct: float) -> str:
    if pct >= cfg.STORAGE_EMERGENCY_PCT:
        return "emergency"
    if pct >= cfg.STORAGE_CRITICAL_PCT:
        return "critical"
    if pct >= cfg.STORAGE_WARN_PCT:
        return "warn"
    return "ok"


def _get_version() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
            cwd=str(cfg.BASE_DIR),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


# ── Serve React frontend ──────────────────────────────────────────────────────
_FRONTEND_DIST = cfg.BASE_DIR / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(request: Request, full_path: str):
        # API routes already handled above; everything else → index.html
        index = _FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse(
            {"detail": "Frontend not built. Run: cd frontend && npm run build"},
            status_code=503,
        )
else:
    @app.get("/", include_in_schema=False)
    async def no_frontend():
        return JSONResponse({
            "detail": "Frontend not built. Run: cd frontend && npm run build",
            "api_docs": "/docs",
        })
