"""Tests for routes/system_endpoints.py."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import system_endpoints as se


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    app = FastAPI()
    app.include_router(se.router)
    se.inject_state(model_id="lima-test", model_created=1234567890, loaded_modules={"m": "ok"})
    return TestClient(app)


def test_list_models_requires_auth(client):
    assert client.get("/v1/models").status_code == 401


def test_list_models_returns_model_list(client):
    response = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert any(m["id"] == "lima-test" for m in data)


@patch.object(se.ws_ticket, "issue", return_value="ticket-abc")
def test_create_ws_ticket(mock_issue, client):
    response = client.post("/v1/ws/ticket", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json()["ticket"] == "ticket-abc"
    assert response.json()["expires_in"] == se.ws_ticket.TTL_SECONDS


@patch.object(se.server_lifespan, "get_startup_state")
@patch.object(se.server_lifespan, "STARTUP_PHASES", ["init", "ready"])
def test_health_ok(mock_state, client):
    mock_state.return_value = {"status": "ready", "errors": [], "pending_warm": []}
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model"] == "lima-test"
    assert payload["startup"]["phases"] == ["init", "ready"]


@patch.object(se.server_lifespan, "get_startup_state")
def test_health_degraded_on_error(mock_state, client):
    mock_state.return_value = {"status": "error", "errors": [{"phase": "db"}], "pending_warm": []}
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_live_key_missing_env(client):
    response = client.get("/api/live-key", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 503


def test_live_key_with_env(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_KEY", "gkey")
    response = client.get("/api/live-key", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["auth"] == "server_side_only"


@patch.object(se, "BACKENDS", {"backend-a": {}, "backend-b": {}})
@patch.object(se.health_state, "get_backend_quality", return_value={"total_requests": 0, "empty_count": 0, "error_msg_count": 0})
@patch.object(se.health_tracker, "is_cooled_down", return_value=False)
@patch.object(se.health_state, "get_backend_state", return_value={"state": "ok"})
@patch.object(se.health_state, "get_latency_map", return_value={})
def test_router_status_summary(mock_lat, mock_state, mock_cool, mock_quality, client):
    response = client.get("/v1/status", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert "backend-a" in payload["backends"]
    assert "backend-a" in payload["circuit_breakers"]
