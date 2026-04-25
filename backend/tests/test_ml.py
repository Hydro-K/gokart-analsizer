"""ML: feature extraction, KMeans bootstrap, style label assignment."""
import numpy as np
import pytest


def _make_lap(lap_num=1, base_speed=12.0):
    from backend.analysis.lap_analyzer import LapData
    t = np.linspace(0, 60, 601)
    s = base_speed + 3 * np.sin(t * 0.3)
    return LapData(lap_number=lap_num, start_idx=0, end_idx=600, lap_time=60.0, time=t, speed=s)


def test_feature_extractor_returns_5_keys():
    from backend.analysis.ml.feature_extractor import extract_features
    lap = _make_lap()
    feats = extract_features(lap)
    assert set(feats.keys()) == {
        "throttle_variance", "braking_intensity",
        "corner_entry_speed_avg", "accel_consistency", "smoothness_score"
    }
    for v in feats.values():
        assert 0.0 <= v <= 100.0


def test_feature_short_lap_returns_zeros():
    from backend.analysis.ml.feature_extractor import extract_features
    from backend.analysis.lap_analyzer import LapData
    lap = LapData(lap_number=1, start_idx=0, end_idx=4, lap_time=1.0,
                  time=np.linspace(0, 1, 5), speed=np.ones(5) * 10)
    feats = extract_features(lap)
    assert all(v == 0.0 for v in feats.values())


def _insert_feature_rows(db, n=25):
    import random
    db.execute("INSERT OR IGNORE INTO drivers(name) VALUES('mldriver')")
    driver_id = db.execute("SELECT id FROM drivers WHERE name='mldriver'").fetchone()[0]
    db.execute("INSERT OR IGNORE INTO karts(name) VALUES('mlkart')")
    kart_id = db.execute("SELECT id FROM karts WHERE name='mlkart'").fetchone()[0]
    db.execute("INSERT OR IGNORE INTO tracks(name) VALUES('mltrack')")
    track_id = db.execute("SELECT id FROM tracks WHERE name='mltrack'").fetchone()[0]
    db.execute("INSERT OR IGNORE INTO sessions(driver_id,kart_id,track_id,date) VALUES(?,?,?,'2024-01-01')",
               (driver_id, kart_id, track_id))
    session_id = db.execute("SELECT id FROM sessions WHERE driver_id=?", (driver_id,)).fetchone()[0]

    for i in range(n):
        db.execute(
            "INSERT INTO laps(session_id,driver_id,kart_id,track_id,lap_number,lap_time_s) VALUES(?,?,?,?,?,?)",
            (session_id, driver_id, kart_id, track_id, i + 1, 60.0 + random.uniform(-2, 2))
        )
        lap_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO feature_vectors(lap_id, driver_id, throttle_variance, braking_intensity, "
            "corner_entry_speed_avg, accel_consistency, smoothness_score) VALUES(?,?,?,?,?,?,?)",
            (lap_id, driver_id,
             random.uniform(5, 30), random.uniform(10, 60),
             random.uniform(30, 70), random.uniform(40, 90),
             random.uniform(20, 80))
        )
    db.commit()
    return driver_id


def test_ml_training_assigns_style_labels():
    from backend.database import create_connection
    from backend.analysis.ml.clustering import run_ml_training

    db = create_connection()
    driver_id = _insert_feature_rows(db, n=25)
    result = run_ml_training(db)

    assert "laps_trained" in result
    assert result["laps_trained"] == 25

    # Check style label assigned to driver
    row = db.execute("SELECT style_label FROM driver_styles WHERE driver_id=?", (driver_id,)).fetchone()
    assert row is not None
    assert row["style_label"] in ("aggressive", "smooth", "balanced", "inconsistent")
    db.close()
