"""Auth: register, login, token validation, role enforcement."""
import pytest


def test_register_first_admin(client):
    res = client.post("/api/auth/register", json={
        "username": "testadmin", "display_name": "Test Admin", "password": "testpass123", "role": "admin"
    })
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["user"]["role"] == "admin"


def test_register_blocked_after_first(client, admin_token):
    res = client.post("/api/auth/register", json={
        "username": "hacker", "display_name": "Hacker", "password": "x", "role": "admin"
    })
    assert res.status_code == 403


def test_login_valid(client, admin_token):
    res = client.post("/api/auth/login", json={"username": "testadmin", "password": "testpass123"})
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_wrong_password(client):
    res = client.post("/api/auth/login", json={"username": "testadmin", "password": "wrong"})
    assert res.status_code == 401


def test_me_requires_auth(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_returns_user(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["username"] == "testadmin"


def test_admin_only_users_list(client, auth_headers):
    res = client.get("/api/users", headers=auth_headers)
    assert res.status_code == 200


def test_viewer_blocked_from_users(client, admin_token):
    # Create viewer
    client.post("/api/users", json={
        "username": "viewer1", "display_name": "Viewer", "password": "p", "role": "viewer"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    login = client.post("/api/auth/login", json={"username": "viewer1", "password": "p"})
    viewer_token = login.json()["token"]
    res = client.get("/api/users", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res.status_code == 403
