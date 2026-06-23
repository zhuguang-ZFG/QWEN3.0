"""Tests for routes/admin_extra_client_keys.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_extra_client_keys


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    app = FastAPI()
    app.include_router(admin_extra_client_keys.router)
    return TestClient(app)


def _auth_headers():
    return {"Authorization": "Bearer admin-token"}


@pytest.fixture(autouse=True)
def _clean_keys():
    with patch.object(admin_extra_client_keys, "_CLIENT_KEYS", {}):
        yield


def test_list_client_keys_empty(client):
    response = client.get("/api/client-keys", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["keys"] == []


def test_create_client_key(client):
    response = client.post(
        "/api/client-keys",
        headers=_auth_headers(),
        json={"label": "test key", "quota_daily": 500},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["key"]["label"] == "test key"
    assert data["key"]["quota_daily"] == 500
    assert data["key_value"].startswith("lima-")


def test_create_client_key_missing_label(client):
    response = client.post(
        "/api/client-keys",
        headers=_auth_headers(),
        json={"quota_daily": 100},
    )
    assert response.status_code == 400


def test_update_client_key(client):
    create_resp = client.post(
        "/api/client-keys",
        headers=_auth_headers(),
        json={"label": "key1"},
    )
    key_id = create_resp.json()["key"]["key_id"]
    response = client.put(
        f"/api/client-keys/{key_id}",
        headers=_auth_headers(),
        json={"label": "key1 updated", "enabled": False, "quota_daily": 2000},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["key"]["label"] == "key1 updated"
    assert data["key"]["enabled"] is False
    assert data["key"]["quota_daily"] == 2000


def test_update_client_key_not_found(client):
    response = client.put(
        "/api/client-keys/missing",
        headers=_auth_headers(),
        json={"enabled": False},
    )
    assert response.status_code == 404


def test_delete_client_key(client):
    create_resp = client.post(
        "/api/client-keys",
        headers=_auth_headers(),
        json={"label": "key1"},
    )
    key_id = create_resp.json()["key"]["key_id"]
    response = client.delete(f"/api/client-keys/{key_id}", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert key_id not in admin_extra_client_keys._CLIENT_KEYS


def test_delete_client_key_not_found(client):
    response = client.delete("/api/client-keys/missing", headers=_auth_headers())
    assert response.status_code == 404


def test_regenerate_client_key(client):
    create_resp = client.post(
        "/api/client-keys",
        headers=_auth_headers(),
        json={"label": "key1"},
    )
    key_id = create_resp.json()["key"]["key_id"]
    old_masked = admin_extra_client_keys._CLIENT_KEYS[key_id]["key_masked"]
    response = client.post(f"/api/client-keys/{key_id}/regenerate", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["key_value"].startswith("lima-")
    assert admin_extra_client_keys._CLIENT_KEYS[key_id]["key_masked"] != old_masked
    assert "regenerated_at" in admin_extra_client_keys._CLIENT_KEYS[key_id]


def test_regenerate_client_key_not_found(client):
    response = client.post("/api/client-keys/missing/regenerate", headers=_auth_headers())
    assert response.status_code == 404
