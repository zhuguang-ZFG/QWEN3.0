"""Tests for routes/admin_api.py."""

from __future__ import annotations

import json
import threading
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_api
from routes import admin_state


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    stats = {
        "start_time": 0,
        "total_requests": 3,
        "backend_calls": {"be1": 2, "be2": 1},
        "intent_distribution": {"chat": 2, "code": 1},
        "recent_logs": [
            {"ip": "1.1.1.1", "ide": "vscode"},
            {"ip": "2.2.2.2", "ide": "pycharm"},
        ],
    }
    admin_state.inject_state(stats, threading.Lock(), {"be1": True, "be2": False})
    app = FastAPI()
    app.include_router(admin_api.router)
    return TestClient(app)


def _auth_headers():
    return {"Authorization": "Bearer admin-token"}


def _backend_mocks():
    backends = {
        "be1": {"url": "https://example.com/v1", "model": "m1", "fmt": "openai", "key": "k1"},
        "be2": {"url": "https://api.anthropic.com/v1", "model": "m2", "fmt": "anthropic", "key": "k2"},
    }

    def add_backend(name, cfg):
        backends[name] = dict(cfg)

    def has_backend(name):
        return name in backends

    def remove_backend(name):
        return backends.pop(name, None) is not None

    return backends, add_backend, has_backend, remove_backend


@patch.object(admin_api, "backend_call_detail", return_value={"total_ms": 100, "count": 1})
def test_admin_stats(_mock_detail, client):
    response = client.get("/api/stats", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["total_requests"] == 3
    assert data["uptime_seconds"] > 0
    assert data["unique_ips"] == 2
    assert "vscode" in data["ide_distribution"]


def test_admin_logs(client):
    response = client.get("/api/logs", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_admin_backends_list(client):
    backends = {
        "be1": {"url": "https://example.com", "model": "m1", "fmt": "openai"},
        "be2": {"url": "https://api.anthropic.com", "model": "m2", "fmt": "anthropic"},
    }
    with patch.object(admin_api, "BACKENDS", backends):
        with patch(
            "health_state.get_backend_quality",
            return_value={"total_requests": 10, "empty_count": 1, "error_msg_count": 0},
        ):
            with patch("health_tracker.is_cooled_down", return_value=False):
                response = client.get("/api/backends", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    names = {b["name"] for b in data}
    assert "be1" in names
    assert "be2" in names


def test_admin_add_backend_success(client):
    backends, add_backend, has_backend, remove_backend = _backend_mocks()
    with patch.object(admin_api, "BACKENDS", backends):
        with patch.object(admin_api, "add_backend", side_effect=add_backend):
            with patch.object(admin_api, "has_backend", side_effect=has_backend):
                with patch.object(admin_api, "test_backend_sync", return_value={"ok": True, "latency_ms": 12}):
                    with patch.object(admin_api, "_is_safe_backend_url", return_value=True):
                        response = client.post(
                            "/api/backends",
                            headers=_auth_headers(),
                            json={
                                "name": "newbe",
                                "url": "https://new.example.com/v1",
                                "key": "secret",
                                "model": "m3",
                                "fmt": "openai",
                            },
                        )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "newbe" in data["message"]


def test_admin_add_backend_missing_name(client):
    response = client.post(
        "/api/backends",
        headers=_auth_headers(),
        json={"url": "https://example.com"},
    )
    assert response.status_code == 400


def test_admin_add_backend_unsafe_url(client):
    response = client.post(
        "/api/backends",
        headers=_auth_headers(),
        json={"name": "bad", "url": "http://localhost:1234"},
    )
    assert response.status_code == 400


def test_admin_add_backend_already_exists(client):
    backends, add_backend, has_backend, _remove = _backend_mocks()
    with patch.object(admin_api, "BACKENDS", backends):
        with patch.object(admin_api, "add_backend", side_effect=add_backend):
            with patch.object(admin_api, "has_backend", side_effect=has_backend):
                with patch.object(admin_api, "_is_safe_backend_url", return_value=True):
                    response = client.post(
                        "/api/backends",
                        headers=_auth_headers(),
                        json={"name": "be1", "url": "https://example.com/v1"},
                    )
    assert response.status_code == 409


def test_admin_delete_backend(client):
    backends, _add, has_backend, remove_backend = _backend_mocks()
    with patch.object(admin_api, "BACKENDS", backends):
        with patch.object(admin_api, "has_backend", side_effect=has_backend):
            with patch.object(admin_api, "remove_backend", side_effect=remove_backend):
                response = client.delete("/api/backends/be1", headers=_auth_headers())
    assert response.status_code == 200
    assert "be1" in response.json()["message"]


def test_admin_delete_backend_not_found(client):
    backends, _add, has_backend, remove_backend = _backend_mocks()
    with patch.object(admin_api, "BACKENDS", backends):
        with patch.object(admin_api, "has_backend", side_effect=has_backend):
            with patch.object(admin_api, "remove_backend", side_effect=remove_backend):
                response = client.delete("/api/backends/missing", headers=_auth_headers())
    assert response.status_code == 404


def test_admin_toggle_backend(client):
    backends = {"be1": {}}
    enabled = {"be1": True}
    admin_state.inject_state({}, threading.Lock(), enabled)
    with patch.object(admin_api, "BACKENDS", backends):
        response = client.post("/api/backends/be1/toggle", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert enabled["be1"] is False


def test_admin_toggle_backend_not_found(client):
    with patch.object(admin_api, "BACKENDS", {}):
        response = client.post("/api/backends/missing/toggle", headers=_auth_headers())
    assert response.status_code == 404


def test_admin_test_backend(client):
    backends = {"be1": {}}
    with patch.object(admin_api, "BACKENDS", backends):
        with patch.object(admin_api, "test_backend_sync", return_value={"ok": True, "latency_ms": 5}):
            response = client.post("/api/backends/be1/test", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["ok"] is True


@patch.object(admin_api, "FALLBACK_LOG", "/tmp/nonexistent_fallback_log.jsonl")
@patch("routes.admin_api.os.path.exists", return_value=False)
def test_admin_model_status_no_log(_mock_exists, client):
    response = client.get("/api/model-status", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["fallback_log_count"] == 0
    assert data["recent_fallbacks"] == []


@patch("routes.admin_api.os.path.exists", return_value=True)
@patch("builtins.open")
def test_admin_model_status_with_log(mock_open, _mock_exists, client):
    mock_open.return_value.__enter__.return_value.readlines.return_value = [
        json.dumps({"backend": "be1", "reason": "timeout"}),
        "not-json",
    ]
    response = client.get("/api/model-status", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["fallback_log_count"] == 2
    assert len(data["recent_fallbacks"]) == 1


@patch.object(admin_api, "list_family_approvals", return_value=[])
def test_admin_list_family_approvals(_mock, client):
    response = client.get("/api/devices/dev1/families", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["deviceId"] == "dev1"
    assert data["families"] == []


class _FakeApproval:
    device_id = "dev1"
    family = "display"
    status = "approved"
    approved_by = "admin"
    approved_at = 1.0
    revoked_at = None
    evidence = {}


@patch.object(admin_api, "list_family_approvals", return_value=[_FakeApproval()])
def test_admin_list_family_approvals_with_records(_mock, client):
    response = client.get("/api/devices/dev1/families", headers=_auth_headers())
    data = response.json()
    assert len(data["families"]) == 1
    assert data["families"][0]["family"] == "display"


@patch.object(
    admin_api,
    "approve_family",
    return_value=_FakeApproval(),
)
def test_admin_approve_family(_mock, client):
    response = client.post(
        "/api/devices/dev1/families/display/approve",
        headers=_auth_headers(),
        json={"evidence": {"note": "ok"}, "approvedBy": "alice"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["family"] == "display"
    assert data["status"] == "approved"


@patch.object(admin_api, "revoke_family", return_value=_FakeApproval())
def test_admin_revoke_family(_mock, client):
    response = client.post(
        "/api/devices/dev1/families/display/revoke",
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["family"] == "display"


@patch.object(admin_api, "revoke_family", return_value=None)
def test_admin_revoke_family_not_found(_mock, client):
    response = client.post(
        "/api/devices/dev1/families/display/revoke",
        headers=_auth_headers(),
    )
    assert response.status_code == 404
