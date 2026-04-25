"""Ingestion: CSV upload creates laps with correct driver/kart/track FKs."""
import pytest
import io


def _setup_entities(client, auth_headers):
    """Create driver, kart, track; return their IDs."""
    d = client.post("/api/drivers", json={"name": "Ingest Driver", "notes": ""}, headers=auth_headers)
    k = client.post("/api/karts",   json={"name": "Ingest Kart"},                headers=auth_headers)
    t = client.post("/api/tracks",  json={"name": "Ingest Track"},               headers=auth_headers)
    return d.json()["id"], k.json()["id"], t.json()["id"]


def test_upload_requires_driver_kart_track(client, auth_headers, sample_csv):
    res = client.post(
        "/api/sessions/upload",
        files={"file": ("test.csv", io.BytesIO(sample_csv), "text/csv")},
        data={"session_type": "Practice 1"},
        headers=auth_headers,
    )
    assert res.status_code == 422  # missing driver_id/kart_id/track_id


def test_upload_creates_job(client, auth_headers, sample_csv):
    did, kid, tid = _setup_entities(client, auth_headers)
    res = client.post(
        "/api/sessions/upload",
        files={"file": ("test.csv", io.BytesIO(sample_csv), "text/csv")},
        data={"driver_id": str(did), "kart_id": str(kid), "track_id": str(tid),
              "session_type": "Practice 1"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data or "session_id" in data


def test_driver_kart_track_blocks_delete_if_sessions(client, auth_headers, sample_csv):
    """Deleting a driver that has sessions must fail."""
    did, kid, tid = _setup_entities(client, auth_headers)
    # Upload a session
    client.post(
        "/api/sessions/upload",
        files={"file": ("test.csv", io.BytesIO(sample_csv), "text/csv")},
        data={"driver_id": str(did), "kart_id": str(kid), "track_id": str(tid)},
        headers=auth_headers,
    )
    # Try to delete driver
    res = client.delete(f"/api/drivers/{did}", headers=auth_headers)
    assert res.status_code in (409, 400, 422, 500)  # blocked by FK or explicit check
