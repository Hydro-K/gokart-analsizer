"""Compliance: 220A cap, rules CRUD, check endpoint."""
import pytest


def test_get_rules(client, auth_headers):
    res = client.get("/api/compliance/rules", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["controller_max_current_a"] == 220.0


def test_update_rules(client, auth_headers):
    res = client.put("/api/compliance/rules", json={
        "controller_max_current_a": 200.0,
        "speed_limit_kmh": 80.0,
    }, headers=auth_headers)
    assert res.status_code == 200

    # Verify persistence
    res2 = client.get("/api/compliance/rules", headers=auth_headers)
    assert res2.json()["controller_max_current_a"] == 200.0


def test_simulation_220a_hard_cap(client, auth_headers):
    """Mode A simulation must cap current at 220A even if 250 requested."""
    from backend.schemas import SimInputA
    req = SimInputA(session_id=1, lap_id=1, max_current=250)
    assert req.max_current == 220  # hard-capped by validator


def test_compliance_check_endpoint(client, auth_headers):
    kart = client.post("/api/karts", json={"name": "ComplianceKart"}, headers=auth_headers)
    kart_id = kart.json()["id"]
    res = client.post(f"/api/compliance/check?kart_id={kart_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "passed" in data
    assert "items" in data
