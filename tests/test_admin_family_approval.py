"""Tests for admin family-approval endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import device_gateway.family_approval_store as store
from routes.admin_api import router as admin_router


@pytest.fixture(autouse=True)
def _isolate_approvals(tmp_path, monkeypatch):
    db_path = str(tmp_path / "admin_family.db")
    monkeypatch.setenv("LIMA_DB_PATH", db_path)
    store.set_db_path(db_path)
    store.reset_family_approvals()
    yield
    store.reset_family_approvals()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "super-secret-admin-token")
    app = FastAPI()
    app.include_router(admin_router)
    return TestClient(app)


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer super-secret-admin-token"}


def test_list_family_approvals_empty(client):
    response = client.get("/api/devices/d-1/families", headers=_headers())
    assert response.status_code == 200
    assert response.json()["deviceId"] == "d-1"
    assert response.json()["families"] == []


def test_approve_and_list_family(client):
    response = client.post(
        "/api/devices/d-1/families/display/approve",
        headers=_headers(),
        json={"evidence": {"safety_test": "passed"}, "approvedBy": "ops"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["family"] == "display"
    assert data["status"] == "approved"
    assert data["approvedBy"] == "ops"

    response = client.get("/api/devices/d-1/families", headers=_headers())
    assert response.status_code == 200
    families = response.json()["families"]
    assert len(families) == 1
    assert families[0]["evidence"] == {"safety_test": "passed"}


def test_revoke_family(client):
    client.post("/api/devices/d-1/families/audio/approve", headers=_headers(), json={})
    response = client.post("/api/devices/d-1/families/audio/revoke", headers=_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"

    response = client.get("/api/devices/d-1/families", headers=_headers())
    assert response.json()["families"][0]["status"] == "revoked"


def test_revoke_missing_family_returns_404(client):
    response = client.post("/api/devices/d-1/families/speech/revoke", headers=_headers())
    assert response.status_code == 404


def test_unauthorized_request_rejected(client):
    response = client.get("/api/devices/d-1/families")
    assert response.status_code == 401
