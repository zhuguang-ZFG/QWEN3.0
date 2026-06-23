"""Tests for routes/token_sync.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.token_sync as ts


@pytest.fixture(autouse=True)
def _reset_overrides():
    ts._token_overrides.clear()
    yield
    ts._token_overrides.clear()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    app = FastAPI()
    app.include_router(ts.router)
    return TestClient(app)


@patch.object(ts, "_validate_token", return_value=True)
@patch("backends_registry.BACKENDS", {"longcat": {"url": "http://u", "model": "m"}})
def test_sync_tokens_updates_and_validates(mock_validate, client):
    response = client.post(
        "/internal/v1/token-sync",
        headers={"Authorization": "Bearer test-key"},
        json={"tokens": {"longcat": "new-key"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"] == ["longcat"]
    assert payload["validated"] == ["longcat"]
    assert payload["total_overrides"] == 1
    assert ts.get_token_override("longcat") == "new-key"


@patch("backends_registry.BACKENDS", {"longcat": {"url": "http://u", "model": "m"}})
def test_sync_tokens_unknown_backend(client):
    response = client.post(
        "/internal/v1/token-sync",
        headers={"Authorization": "Bearer test-key"},
        json={"tokens": {"unknown": "key"}},
    )
    assert response.status_code == 200
    assert "unknown backend" in response.json()["failed"][0]


@patch.object(ts, "_validate_token", return_value=False)
@patch("backends_registry.BACKENDS", {"longcat": {"url": "http://u", "model": "m"}})
def test_sync_tokens_validation_failure(mock_validate, client):
    response = client.post(
        "/internal/v1/token-sync",
        headers={"Authorization": "Bearer test-key"},
        json={"tokens": {"longcat": "bad-key"}},
    )
    assert response.status_code == 200
    assert "validation failed" in response.json()["failed"][0]
    assert ts.get_token_override("longcat") is None


def test_sync_tokens_requires_auth(client):
    response = client.post("/internal/v1/token-sync", json={"tokens": {}})
    assert response.status_code == 401


@patch("backends_registry.BACKENDS", {"longcat": {"url": "http://u", "model": "m", "key": "orig"}})
def test_token_sync_status(client):
    ts._token_overrides["longcat"] = "override-key-long"
    response = client.get("/internal/v1/token-sync/status", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    status = response.json()["backends"]["longcat"]
    assert status["has_override"] is True
    assert "override-key-long"[:15] in status["key_preview"]
