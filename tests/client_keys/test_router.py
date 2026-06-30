"""Tests for client_keys admin API routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import client_keys
from routes.admin_auth import verify_admin, verify_csrf
from routes.client_keys import router


def _mock_verify_admin():
    return None


def _mock_verify_csrf():
    return None


@pytest.fixture
def app(monkeypatch, tmp_path):
    db_path = tmp_path / "client_keys.db"
    client_keys.reset_for_tests(str(db_path))
    app = FastAPI()
    app.dependency_overrides[verify_admin] = _mock_verify_admin
    app.dependency_overrides[verify_csrf] = _mock_verify_csrf
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_list_empty(client):
    resp = client.get("/admin/api/client-keys")
    assert resp.status_code == 200
    data = resp.json()
    assert data["keys"] == []
    assert data["total"] == 0


def test_create_and_list(client):
    resp = client.post("/admin/api/client-keys", json={"label": "cursor-user"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "key_value" not in data

    resp = client.get("/admin/api/client-keys")
    keys = resp.json()["keys"]
    assert len(keys) == 1
    assert keys[0]["label"] == "cursor-user"


def test_create_with_reveal(client):
    resp = client.post(
        "/admin/api/client-keys",
        json={"label": "revealed", "reveal": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["key_value"].startswith("lima-")


def test_create_rejects_empty_label(client):
    resp = client.post("/admin/api/client-keys", json={"label": ""})
    assert resp.status_code == 422


def test_create_rejects_negative_quota(client):
    resp = client.post("/admin/api/client-keys", json={"label": "x", "quota_daily": -1})
    assert resp.status_code == 422


def test_update(client):
    resp = client.post("/admin/api/client-keys", json={"label": "to-update"})
    key_id = resp.json()["key_id"]

    resp = client.put(f"/admin/api/client-keys/{key_id}", json={"enabled": False})
    assert resp.status_code == 200

    resp = client.get("/admin/api/client-keys")
    assert resp.json()["keys"][0]["enabled"] is False


def test_update_not_found(client):
    resp = client.put("/admin/api/client-keys/ck-missing", json={"enabled": False})
    assert resp.status_code == 404


def test_delete(client):
    resp = client.post("/admin/api/client-keys", json={"label": "to-delete"})
    key_id = resp.json()["key_id"]

    resp = client.delete(f"/admin/api/client-keys/{key_id}")
    assert resp.status_code == 200

    resp = client.get("/admin/api/client-keys")
    assert resp.json()["total"] == 0


def test_regenerate(client):
    resp = client.post("/admin/api/client-keys", json={"label": "regen", "reveal": True})
    data = resp.json()
    key_id = data["key_id"]
    old_value = data["key_value"]

    resp = client.post(f"/admin/api/client-keys/{key_id}/regenerate", json={})
    assert resp.status_code == 200
    assert "key_value" not in resp.json()

    resp = client.post(
        f"/admin/api/client-keys/{key_id}/regenerate",
        json={"reveal": True},
    )
    new_value = resp.json()["key_value"]
    assert new_value != old_value


def test_regenerate_not_found(client):
    resp = client.post("/admin/api/client-keys/ck-missing/regenerate", json={})
    assert resp.status_code == 404
