"""Tests for routes/admin_extra_insights.py."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_extra_insights
from routes import admin_state


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    app = FastAPI()
    app.include_router(admin_extra_insights.router)
    return TestClient(app)


def _auth_headers():
    return {"Authorization": "Bearer admin-token"}


def test_fallback_analysis_no_log(client, monkeypatch):
    monkeypatch.setattr(admin_state, "FALLBACK_LOG", "/tmp/lima_fallback_missing.jsonl")
    response = client.get("/api/fallback-analysis", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["by_backend"] == []


@patch("builtins.open")
def test_fallback_analysis_with_entries(mock_open, client, monkeypatch):
    monkeypatch.setattr(admin_state, "FALLBACK_LOG", "/tmp/lima_fallback.jsonl")
    mock_open.return_value.__enter__.return_value = iter(
        [
            json.dumps({"original_backend": "be1", "intent": "code", "timestamp": "2026-06-23T10:00:00"}),
            json.dumps({"backend": "be2", "reason": "timeout", "time": "2026-06-23T11:00:00"}),
            "not-json\n",
        ]
    )
    with patch("routes.admin_extra_insights.os.path.exists", return_value=True):
        response = client.get("/api/fallback-analysis", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["by_backend"][0]["backend"] == "be1"


def test_key_url_inventory(client):
    backends = {
        "be1": {"url": "https://example.com", "key": "super-secret-key", "model": "m1", "fmt": "openai"},
        "be2": {"url": "https://api.anthropic.com", "key": "", "model": "m2", "fmt": "anthropic"},
    }
    with patch.object(admin_extra_insights, "BACKENDS", backends):
        response = client.get("/api/key-url-inventory", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert len(data["backends"]) == 2
    be1 = next(b for b in data["backends"] if b["name"] == "be1")
    assert be1["key_configured"] is True
    assert "..." in be1["key_masked"]
    be2 = next(b for b in data["backends"] if b["name"] == "be2")
    assert be2["key_configured"] is False


def test_key_url_inventory_with_pool(client):
    with patch.object(admin_extra_insights, "BACKENDS", {}):
        with patch("key_pool.get_pool_status", return_value={"provider-a": {"available": 1}}, create=True):
            response = client.get("/api/key-url-inventory", headers=_auth_headers())
    data = response.json()
    assert data["key_pools"]["providers"]["provider-a"]["available"] == 1


def test_retrain_jobs(client):
    response = client.get("/api/retrain/jobs", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["jobs"] == []


def test_trigger_retrain(client):
    response = client.post("/api/retrain", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "retired"


def test_agent_audit(client):
    response = client.get("/api/agent-audit", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["tasks"] == []
