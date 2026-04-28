"""SQLite database connection and schema initialization for Strat-OS."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Generator

import backend.config as cfg

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

-- ── Auth ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE,
    display_name  TEXT    NOT NULL,
    role          TEXT    DEFAULT 'engineer',
    password_hash TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS auth_tokens (
    token      TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT    NOT NULL
);

-- ── Core entities ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drivers (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL UNIQUE,
    notes      TEXT    DEFAULT '',
    created_at TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS karts (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    motor_type    TEXT    DEFAULT 'DC Series',
    battery_type  TEXT    DEFAULT 'LiFePO4',
    mass_kg       REAL    DEFAULT 115.0,
    settings_json TEXT    DEFAULT '{}',
    gear_json     TEXT    DEFAULT '{}',
    notes         TEXT    DEFAULT '',
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS tracks (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    lat_center REAL,
    lon_center REAL,
    length_m   REAL,
    gps_points BLOB,
    local_xy   BLOB,
    created_at TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ── Sessions ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id             INTEGER PRIMARY KEY,
    driver_id      INTEGER NOT NULL REFERENCES drivers(id) ON DELETE RESTRICT,
    kart_id        INTEGER NOT NULL REFERENCES karts(id)   ON DELETE RESTRICT,
    track_id       INTEGER NOT NULL REFERENCES tracks(id)  ON DELETE RESTRICT,
    date           TEXT    NOT NULL,
    session_type   TEXT    DEFAULT 'Practice 1',
    raw_file_path  TEXT,
    notes          TEXT    DEFAULT '',
    created_at     TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_driver ON sessions(driver_id);
CREATE INDEX IF NOT EXISTS idx_sessions_kart   ON sessions(kart_id);
CREATE INDEX IF NOT EXISTS idx_sessions_date   ON sessions(date);

-- ── Laps ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS laps (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    driver_id   INTEGER NOT NULL REFERENCES drivers(id),
    kart_id     INTEGER NOT NULL REFERENCES karts(id),
    track_id    INTEGER NOT NULL REFERENCES tracks(id),
    lap_number  INTEGER NOT NULL,
    lap_time_s  REAL    NOT NULL,
    is_valid    INTEGER DEFAULT 1,
    created_at  TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_laps_session ON laps(session_id);
CREATE INDEX IF NOT EXISTS idx_laps_driver  ON laps(driver_id);
CREATE INDEX IF NOT EXISTS idx_laps_time    ON laps(lap_time_s);

-- ── Lap telemetry ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lap_telemetry (
    id              INTEGER PRIMARY KEY,
    lap_id          INTEGER NOT NULL UNIQUE REFERENCES laps(id) ON DELETE CASCADE,
    time_json       TEXT    NOT NULL,
    speed_json      TEXT    NOT NULL,
    lat_json        TEXT,
    lon_json        TEXT,
    phase_json      TEXT,
    lateral_acc_json   TEXT,
    inline_acc_json    TEXT,
    yaw_rate_json      TEXT,
    roll_rate_json     TEXT,
    pitch_rate_json    TEXT,
    vertical_acc_json  TEXT,
    battery_v_json     TEXT
);

-- ── ML ────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feature_vectors (
    id                     INTEGER PRIMARY KEY,
    lap_id                 INTEGER NOT NULL UNIQUE REFERENCES laps(id) ON DELETE CASCADE,
    driver_id              INTEGER NOT NULL REFERENCES drivers(id),
    throttle_variance      REAL,
    braking_intensity      REAL,
    corner_entry_speed_avg REAL,
    accel_consistency      REAL,
    smoothness_score       REAL,
    style_label            TEXT,
    created_at             TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_features_driver ON feature_vectors(driver_id);

CREATE TABLE IF NOT EXISTS driver_styles (
    id                INTEGER PRIMARY KEY,
    driver_id         INTEGER NOT NULL UNIQUE REFERENCES drivers(id) ON DELETE CASCADE,
    style_label       TEXT    NOT NULL,
    confidence        REAL    DEFAULT 0.0,
    sessions_analyzed INTEGER DEFAULT 0,
    updated_at        TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ── Setup history ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kart_setups (
    id            INTEGER PRIMARY KEY,
    kart_id       INTEGER NOT NULL REFERENCES karts(id) ON DELETE CASCADE,
    session_id    INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    settings_json TEXT    NOT NULL,
    gear_json     TEXT    NOT NULL,
    notes         TEXT    DEFAULT '',
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_setups_kart ON kart_setups(kart_id);

-- ── Post-session readings ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS post_session_readings (
    id                 INTEGER PRIMARY KEY,
    session_id         INTEGER NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
    tyre_temp_fl       REAL, tyre_temp_fr  REAL, tyre_temp_rl REAL, tyre_temp_rr REAL,
    tyre_psi_fl        REAL, tyre_psi_fr   REAL, tyre_psi_rl  REAL, tyre_psi_rr  REAL,
    motor_temp_c       REAL,
    controller_temp_c  REAL,
    battery_temp_c     REAL,
    battery_voltage_v  REAL,
    battery_soc_pct    REAL,
    brake_temp_fl      REAL, brake_temp_fr REAL, brake_temp_rl REAL, brake_temp_rr REAL,
    notes              TEXT DEFAULT '',
    created_at         TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ── Simulation results ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS simulation_results (
    id            INTEGER PRIMARY KEY,
    session_id    INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    lap_id        INTEGER REFERENCES laps(id) ON DELETE CASCADE,
    mode          TEXT    NOT NULL,
    goal          TEXT    DEFAULT 'lap_time',
    weight_speed  REAL    DEFAULT 0.5,
    weight_energy REAL    DEFAULT 0.5,
    lap_time_s    REAL,
    energy_kwh    REAL,
    delta_json    TEXT,
    inputs_json   TEXT,
    created_at    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_simresults_session ON simulation_results(session_id);

-- ── Benchmarks ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS benchmarks (
    id                 INTEGER PRIMARY KEY,
    track_id           INTEGER NOT NULL REFERENCES tracks(id)  ON DELETE CASCADE,
    driver_id          INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    kart_id            INTEGER NOT NULL REFERENCES karts(id)   ON DELETE CASCADE,
    best_ever_s        REAL,
    best_session_s     REAL,
    theoretical_best_s REAL,
    updated_at         TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(track_id, driver_id, kart_id)
);
CREATE INDEX IF NOT EXISTS idx_benchmarks_track  ON benchmarks(track_id);
CREATE INDEX IF NOT EXISTS idx_benchmarks_driver ON benchmarks(driver_id);

-- ── Job queue ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY,
    type         TEXT    NOT NULL,
    status       TEXT    DEFAULT 'pending',
    priority     INTEGER DEFAULT 5,
    payload_json TEXT    DEFAULT '{}',
    result_json  TEXT,
    error_msg    TEXT,
    worker_id    TEXT,
    created_at   TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at   TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, priority);

-- ── Storage archive ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS storage_archive (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tier        TEXT    NOT NULL,
    archive_path TEXT,
    archived_at TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ── Weather logs ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weather_logs (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    temp_f          REAL,
    humidity_pct    REAL,
    track_condition TEXT    DEFAULT 'dry',
    notes           TEXT    DEFAULT '',
    created_at      TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ── Maintenance logs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS maintenance_logs (
    id           INTEGER PRIMARY KEY,
    kart_id      INTEGER NOT NULL REFERENCES karts(id) ON DELETE CASCADE,
    type         TEXT    NOT NULL,
    description  TEXT    DEFAULT '',
    date         TEXT    NOT NULL,
    laps_at_service INTEGER DEFAULT 0,
    next_due_laps   INTEGER,
    created_at   TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_maintenance_kart ON maintenance_logs(kart_id);

-- ── Checklists ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS checklist_templates (
    id         INTEGER PRIMARY KEY,
    kart_id    INTEGER REFERENCES karts(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    items_json TEXT    DEFAULT '[]',
    created_at TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS checklist_runs (
    id             INTEGER PRIMARY KEY,
    template_id    INTEGER NOT NULL REFERENCES checklist_templates(id) ON DELETE CASCADE,
    session_id     INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    checked_json   TEXT    DEFAULT '[]',
    completed_at   TEXT,
    created_at     TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ── Competition rules (single row) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS competition_rules (
    id                       INTEGER PRIMARY KEY DEFAULT 1,
    controller_max_current_a REAL DEFAULT 220.0,
    battery_voltage_nominal_v REAL DEFAULT 51.2,
    battery_voltage_max_v    REAL DEFAULT 58.4,
    battery_voltage_min_v    REAL DEFAULT 40.0,
    battery_capacity_wh      REAL DEFAULT 3072.0,
    speed_limit_kmh          REAL DEFAULT 80.0,
    combined_min_weight_kg   REAL DEFAULT 181.4,
    rulebook_version         TEXT DEFAULT '2025-26',
    updated_at               TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
INSERT OR IGNORE INTO competition_rules (id) VALUES (1);
"""


def get_db_path() -> Path:
    return cfg.DB_PATH


def create_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    cfg.ensure_dirs()
    conn = create_connection()
    conn.executescript(_DDL)
    # Safe column additions for existing databases
    _add_columns_if_missing(conn, "lap_telemetry", [
        ("lateral_acc_json",  "TEXT"),
        ("inline_acc_json",   "TEXT"),
        ("yaw_rate_json",     "TEXT"),
        ("roll_rate_json",    "TEXT"),
        ("pitch_rate_json",   "TEXT"),
        ("vertical_acc_json", "TEXT"),
        ("battery_v_json",    "TEXT"),
    ])
    _add_columns_if_missing(conn, "laps", [
        ("recorded_at", "TEXT"),
        ("notes",       "TEXT DEFAULT ''"),
    ])
    _add_columns_if_missing(conn, "sessions", [
        ("start_voltage_v", "REAL"),
    ])
    conn.commit()
    conn.close()


def _add_columns_if_missing(conn: sqlite3.Connection, table: str, cols: list[tuple[str, str]]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for col_name, col_type in cols:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = create_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
