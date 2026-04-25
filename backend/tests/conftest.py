"""Shared test fixtures for Strat-OS backend tests."""
import pytest
import sqlite3
import io
from pathlib import Path
from fastapi.testclient import TestClient

# Point to in-memory DB before any app import
import os
os.environ["STRATOS_DATA_DIR"] = str(Path(__file__).parent / "test_data")

from backend.main import app
from backend.database import init_db, get_db, create_connection
from backend.config import ensure_dirs


@pytest.fixture(scope="session", autouse=True)
def setup_test_env(tmp_path_factory):
    """Initialize a clean test DB in a temp directory."""
    td = tmp_path_factory.mktemp("stratos_test")
    os.environ["STRATOS_DATA_DIR"] = str(td)
    # Re-import config to pick up new DATA_DIR
    import importlib
    import backend.config as cfg
    importlib.reload(cfg)
    import backend.database as db_mod
    importlib.reload(db_mod)
    ensure_dirs()
    init_db()
    yield
    # Cleanup handled by pytest tmp_path


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_token(client):
    """Create admin user and return auth token."""
    res = client.post("/api/auth/register", json={
        "username": "testadmin",
        "display_name": "Test Admin",
        "password": "testpass123",
        "role": "admin",
    })
    # May already exist on second call — try login
    if res.status_code != 200:
        res = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
    return res.json()["token"]


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def sample_csv() -> bytes:
    """Minimal AiM CSV fixture that data_loader can parse."""
    lines = [
        "Format,AIM CSV v2",
        "Device,EVO4S",
        "Vehicle,TestKart",
        "Driver,Test Driver",
        "Date,2024-01-15",
        "Time,10:00:00",
        "Session,Practice",
        "Channel,GPS Speed,GPS Latitude,GPS Longitude",
        "Units,km/h,deg,deg",
        "Frequency,10,10,10",
        "",
        "0.0,45.2,51.5074,-0.1278",
        "0.1,48.3,51.5074,-0.1277",
        "0.2,51.0,51.5075,-0.1276",
        "0.3,53.5,51.5075,-0.1275",
        "0.4,55.1,51.5076,-0.1274",
        "0.5,56.2,51.5077,-0.1273",
        "0.6,57.0,51.5078,-0.1272",
        "0.7,57.5,51.5079,-0.1271",
        "0.8,57.8,51.5080,-0.1270",
        "0.9,58.0,51.5081,-0.1269",
        # Add enough to make ~3 laps...
    ]
    # Generate enough rows for 3 laps ~60s each
    import math
    t = 1.0
    for lap in range(3):
        for step in range(600):  # 60s at 10Hz
            lat = 51.5074 + 0.001 * math.sin(step * math.pi / 300)
            lon = -0.1278 + 0.001 * math.cos(step * math.pi / 300)
            spd = 40.0 + 20.0 * abs(math.sin(step * math.pi / 150))
            lines.append(f"{t:.1f},{spd:.1f},{lat:.6f},{lon:.6f}")
            t += 0.1

    return "\n".join(lines).encode()
