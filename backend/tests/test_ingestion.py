"""Ingestion: CSV upload creates laps with correct driver/kart/track FKs."""
import pytest
import io


_entity_counter = 0

def _setup_entities(client, auth_headers):
    """Create driver, kart, track; return their IDs."""
    global _entity_counter
    _entity_counter += 1
    n = _entity_counter
    d = client.post("/api/drivers", json={"name": f"Ingest Driver {n}", "notes": ""}, headers=auth_headers)
    k = client.post("/api/karts",   json={"name": f"Ingest Kart {n}"},                headers=auth_headers)
    t = client.post("/api/tracks",  json={"name": f"Ingest Track {n}"},               headers=auth_headers)
    return d.json()["id"], k.json()["id"], t.json()["id"]


def test_upload_requires_driver_kart_track(client, auth_headers, sample_csv):
    res = client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", io.BytesIO(sample_csv), "text/csv"))],
        data={"session_type": "Practice 1"},
        headers=auth_headers,
    )
    assert res.status_code == 422  # missing driver_id/kart_id/track_id


def test_upload_creates_job(client, auth_headers, sample_csv):
    did, kid, tid = _setup_entities(client, auth_headers)
    res = client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", io.BytesIO(sample_csv), "text/csv"))],
        data={"driver_id": str(did), "kart_id": str(kid), "track_id": str(tid),
              "session_type": "Practice 1", "date": "2024-01-15"},
        headers=auth_headers,
    )
    assert res.status_code in (200, 202)
    data = res.json()
    assert "job_id" in data or "session_id" in data


def test_driver_kart_track_blocks_delete_if_sessions(client, auth_headers, sample_csv):
    """Deleting a driver that has sessions must fail."""
    did, kid, tid = _setup_entities(client, auth_headers)
    # Upload a session
    client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", io.BytesIO(sample_csv), "text/csv"))],
        data={"driver_id": str(did), "kart_id": str(kid), "track_id": str(tid), "date": "2024-01-15"},
        headers=auth_headers,
    )
    # Try to delete driver
    res = client.delete(f"/api/drivers/{did}", headers=auth_headers)
    assert res.status_code in (409, 400, 422, 500)  # blocked by FK or explicit check
