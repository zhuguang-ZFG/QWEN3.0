"""Tests for routes/admin_extra_config.py."""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_extra_config
from routes import admin_state


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    admin_state.inject_state({}, threading.Lock(), {"be1": True, "be2": False})
    app = FastAPI()
    app.include_router(admin_extra_config.router)
    return TestClient(app)


def _auth_headers():
    return {"Authorization": "Bearer admin-token"}


@pytest.fixture
def backends():
    data = {
        "be1": {"url": "https://example.com", "model": "m1", "fmt": "openai", "tier": "L2", "caps": ["text"]},
    }
    with patch.object(admin_extra_config, "BACKENDS", data):
        yield data


def test_config_export(client, backends):
    response = client.get("/api/config/export", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0"
    assert "be1" in data["backends"]
    assert data["backend_enabled"]["be1"] is True
    assert data["backend_enabled"]["be2"] is False


def test_config_import_new_backends(client, backends):
    with patch.object(admin_extra_config, "add_backend") as mock_add:
        with patch.object(admin_extra_config, "has_backend", return_value=False):
            with patch.object(admin_extra_config, "_is_safe_backend_url", return_value=True):
                response = client.post(
                    "/api/config/import",
                    headers=_auth_headers(),
                    json={
                        "version": "1.0",
                        "backends": {
                            "newbe": {"url": "https://new.example.com", "model": "m2"},
                        },
                    },
                )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "newbe" in data["imported"]
    mock_add.assert_called_once()


def test_config_import_missing_version(client):
    response = client.post(
        "/api/config/import",
        headers=_auth_headers(),
        json={"backends": {}},
    )
    assert response.status_code == 400


def test_config_import_unsafe_url(client, backends):
    with patch.object(admin_extra_config, "has_backend", return_value=False):
        with patch.object(admin_extra_config, "_is_safe_backend_url", return_value=False):
            response = client.post(
                "/api/config/import",
                headers=_auth_headers(),
                json={
                    "version": "1.0",
                    "backends": {"badbe": {"url": "http://localhost:1234"}},
                },
            )
    assert response.status_code == 400
    assert "unsafe" in response.json()["detail"].lower()


def test_config_import_skips_existing(client, backends):
    with patch.object(admin_extra_config, "has_backend", return_value=True):
        response = client.post(
            "/api/config/import",
            headers=_auth_headers(),
            json={
                "version": "1.0",
                "backends": {"be1": {"url": "https://other.com"}},
            },
        )
    assert response.status_code == 200
    assert response.json()["imported"] == []
