"""Tests for routes/admin_extra_backend_edit.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_extra_backend_edit


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    app = FastAPI()
    app.include_router(admin_extra_backend_edit.router)
    return TestClient(app)


def _auth_headers():
    return {"Authorization": "Bearer admin-token"}


@pytest.fixture
def backends():
    data = {
        "be1": {"url": "https://old.example.com", "model": "old-model", "caps": ["text"]},
    }
    with patch.object(admin_extra_backend_edit, "BACKENDS", data):
        yield data


def test_edit_backend_url_and_model(client, backends):
    response = client.put(
        "/api/backends/be1",
        headers=_auth_headers(),
        json={"url": "https://new.example.com", "model": "new-model"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "be1"
    assert backends["be1"]["url"] == "https://new.example.com"
    assert backends["be1"]["model"] == "new-model"


def test_edit_backend_caps_and_admission(client, backends):
    response = client.put(
        "/api/backends/be1",
        headers=_auth_headers(),
        json={"caps": ["vision", "tools"], "admission": "premium"},
    )
    assert response.status_code == 200
    assert backends["be1"]["caps"] == ["vision", "tools"]
    assert backends["be1"]["admission"] == "premium"


def test_edit_backend_not_found(client):
    with patch.object(admin_extra_backend_edit, "BACKENDS", {}):
        response = client.put(
            "/api/backends/missing",
            headers=_auth_headers(),
            json={"url": "https://example.com"},
        )
    assert response.status_code == 404


def test_edit_backend_empty_url_ignored(client, backends):
    original_url = backends["be1"]["url"]
    response = client.put(
        "/api/backends/be1",
        headers=_auth_headers(),
        json={"url": ""},
    )
    assert response.status_code == 200
    assert backends["be1"]["url"] == original_url
