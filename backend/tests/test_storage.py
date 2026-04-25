"""Storage: stats endpoint, archive job creation at threshold."""
import pytest
from unittest.mock import patch


def test_storage_stats_returns_expected_keys(client, auth_headers):
    res = client.get("/api/storage/stats", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "used_pct" in data
    assert "status" in data
    assert "total_gb" in data
    assert data["status"] in ("ok", "warn", "critical", "emergency")


def test_storage_status_ok_when_low(client, auth_headers):
    with patch("shutil.disk_usage") as mock_du:
        mock_du.return_value = type("du", (), {"total": 100 * 1024**3, "used": 50 * 1024**3, "free": 50 * 1024**3})()
        res = client.get("/api/storage/stats", headers=auth_headers)
        # 50% usage = ok
        assert res.json()["status"] == "ok"


def test_storage_status_warn_at_75pct(client, auth_headers):
    with patch("shutil.disk_usage") as mock_du:
        mock_du.return_value = type("du", (), {"total": 100 * 1024**3, "used": 75 * 1024**3, "free": 25 * 1024**3})()
        res = client.get("/api/storage/stats", headers=auth_headers)
        assert res.json()["status"] in ("warn", "critical", "emergency")
