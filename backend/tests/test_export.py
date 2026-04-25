"""Export: session report generates PNG files and report.txt."""
import pytest
import zipfile
from pathlib import Path
import sqlite3
import json
import numpy as np


def _seed_session(db: sqlite3.Connection) -> int:
    """Insert a complete session with 3 laps + telemetry for export test."""
    db.execute("INSERT OR IGNORE INTO drivers(name) VALUES('exportdriver')")
    did = db.execute("SELECT id FROM drivers WHERE name='exportdriver'").fetchone()[0]
    db.execute("INSERT OR IGNORE INTO karts(name) VALUES('exportkart')")
    kid = db.execute("SELECT id FROM karts WHERE name='exportkart'").fetchone()[0]
    db.execute("INSERT OR IGNORE INTO tracks(name) VALUES('exporttrack')")
    tid = db.execute("SELECT id FROM tracks WHERE name='exporttrack'").fetchone()[0]
    db.execute(
        "INSERT INTO sessions(driver_id,kart_id,track_id,date,session_type) VALUES(?,?,?,'2024-02-01','Practice')",
        (did, kid, tid)
    )
    sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    t = list(np.linspace(0, 60, 601))
    s = list(10.0 + 5 * np.sin(np.linspace(0, 60, 601) * 0.2))
    phase = ["accelerating" if x > 0 else "braking" for x in np.gradient(s)]

    for lap_num in range(1, 4):
        db.execute(
            "INSERT INTO laps(session_id,driver_id,kart_id,track_id,lap_number,lap_time_s,is_valid) VALUES(?,?,?,?,?,?,1)",
            (sid, did, kid, tid, lap_num, 60.0 + lap_num)
        )
        lap_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO lap_telemetry(lap_id,time_json,speed_json,phase_json) VALUES(?,?,?,?)",
            (lap_id, json.dumps(t), json.dumps(s), json.dumps(phase))
        )
    db.commit()
    return sid


def test_export_creates_zip_with_report(tmp_path):
    import backend.config as cfg
    cfg.EXPORT_DIR = tmp_path / "exports"
    cfg.EXPORT_DIR.mkdir()

    from backend.database import create_connection
    from backend.services.export_service import export_session

    db = create_connection()
    sid = _seed_session(db)
    result = export_session(sid, db)

    assert "zip_path" in result
    zip_path = Path(result["zip_path"])
    assert zip_path.exists()

    with zipfile.ZipFile(str(zip_path)) as zf:
        names = zf.namelist()

    assert any("report.txt" in n for n in names)
    assert any("report.json" in n for n in names)
    # At least 1 chart PNG
    png_count = sum(1 for n in names if n.endswith(".png"))
    assert png_count >= 1
    db.close()
