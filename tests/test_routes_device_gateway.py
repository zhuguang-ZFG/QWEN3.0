"""Tests for routes/device_gateway.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_gateway as dg


@pytest.fixture(autouse=True)
def _reset_state():
    dg._reset_for_tests()
    yield
    dg._reset_for_tests()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=token-1")
    app = FastAPI()
    app.include_router(dg.router)
    return TestClient(app)


# ── health ───────────────────────────────────────────────────────────────


def test_device_gateway_health_ok(client):
    with patch.object(dg, "build_device_gateway_health", return_value=({"status": "ok"}, True)):
        response = client.get("/device/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_device_gateway_health_degraded(client):
    with patch.object(dg, "build_device_gateway_health", return_value=({"status": "degraded"}, False)):
        response = client.get("/device/v1/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


# ── events ───────────────────────────────────────────────────────────────


def test_device_gateway_events_requires_auth(client):
    assert client.post("/device/v1/events", json={"type": "device_info"}).status_code == 401


def test_device_gateway_events_invalid_json(client):
    response = client.post("/device/v1/events", content="not-json", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 400


def test_device_gateway_events_invalid_protocol(client):
    with patch.object(dg, "validate_uplink", side_effect=dg.ProtocolError("E_PROTOCOL_VERSION", "bad")):
        response = client.post(
            "/device/v1/events",
            json={"type": "hello"},
            headers={"Authorization": "Bearer test-key"},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "E_PROTOCOL_VERSION"


def test_device_gateway_events_motion_event(client):
    message = {"type": "motion_event", "device_id": "dev-1", "task_id": "t1", "phase": "done"}
    with (
        patch.object(dg, "validate_uplink", return_value=message),
        patch.object(dg, "process_motion_event_core", return_value={"phase": "done"}) as mock_process,
    ):
        response = client.post(
            "/device/v1/events",
            json=message,
            headers={"Authorization": "Bearer test-key"},
        )
    assert response.status_code == 200
    assert response.json()["type"] == "motion_event_ack"
    mock_process.assert_called_once_with("dev-1", message)


def test_device_gateway_events_device_info(client):
    message = {"type": "device_info", "device_id": "dev-1"}
    with (
        patch.object(dg, "validate_uplink", return_value=message),
        patch.object(dg.shadow_store, "update_device_info") as mock_update,
    ):
        response = client.post(
            "/device/v1/events",
            json=message,
            headers={"Authorization": "Bearer test-key"},
        )
    assert response.status_code == 200
    assert response.json()["type"] == "device_info_ack"
    mock_update.assert_called_once_with(message)


def test_device_gateway_events_self_check(client):
    message = {"type": "self_check", "device_id": "dev-1", "status": "ok"}
    with (
        patch.object(dg, "validate_uplink", return_value=message),
        patch.object(dg.shadow_store, "update_self_check") as mock_update,
    ):
        response = client.post(
            "/device/v1/events",
            json=message,
            headers={"Authorization": "Bearer test-key"},
        )
    assert response.status_code == 200
    assert response.json()["type"] == "self_check_ack"
    mock_update.assert_called_once_with(message)


def test_device_gateway_events_unsupported_type(client):
    message = {"type": "unsupported", "device_id": "dev-1"}
    with patch.object(dg, "validate_uplink", return_value=message):
        response = client.post(
            "/device/v1/events",
            json=message,
            headers={"Authorization": "Bearer test-key"},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "E_UNSUPPORTED_TYPE"


# ── tasks ────────────────────────────────────────────────────────────────


def test_device_gateway_tasks_requires_auth(client):
    assert client.post("/device/v1/tasks", json={"device_id": "dev-1", "text": "draw"}).status_code == 401


def test_device_gateway_tasks_missing_device_id(client):
    response = client.post(
        "/device/v1/tasks",
        json={"text": "draw"},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 400


def test_device_gateway_tasks_missing_text(client):
    response = client.post(
        "/device/v1/tasks",
        json={"device_id": "dev-1"},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 400


def test_device_gateway_tasks_creates_task(client):
    result = MagicMock()
    result.status = "queued"
    result.sent = False
    result.queue_depth = 1
    result.task = {"task_id": "t1"}
    with (
        patch.object(dg, "create_and_route_task", new_callable=AsyncMock, return_value=result),
        patch.object(dg, "_record_device_task_evidence") as mock_record,
    ):
        response = client.post(
            "/device/v1/tasks",
            json={"device_id": "dev-1", "text": "draw a circle", "request_id": "r1"},
            headers={"Authorization": "Bearer test-key"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["task"]["task_id"] == "t1"
    mock_record.assert_called_once()


# ── ws ticket ────────────────────────────────────────────────────────────


def test_create_device_ws_ticket_missing_device(client):
    response = client.post("/device/v1/ws/ticket", json={"token": "token-1"})
    assert response.status_code == 401


def test_create_device_ws_ticket_invalid_token(client):
    response = client.post("/device/v1/ws/ticket", json={"device_id": "dev-1", "token": "bad"})
    assert response.status_code == 401


def test_create_device_ws_ticket_success(client):
    response = client.post(
        "/device/v1/ws/ticket",
        json={"device_id": "dev-1", "token": "token-1"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "ticket" in payload
    assert payload["expires_in"] == dg.device_ws_ticket.TTL_SECONDS


def test_create_device_ws_ticket_uses_header_token(client):
    response = client.post(
        "/device/v1/ws/ticket",
        json={"device_id": "dev-1"},
        headers={"Authorization": "Bearer token-1"},
    )
    assert response.status_code == 200
    assert "ticket" in response.json()


# ── task status ──────────────────────────────────────────────────────────


def test_device_task_status_not_found(client):
    with patch("device_gateway.tasks.task_snapshot", return_value=None):
        response = client.get("/device/v1/tasks/t1", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 404


def test_device_task_status_found(client):
    snapshot = {"status": "done", "task": {"task_id": "t1"}, "events": [{"phase": "done"}]}
    with patch("device_gateway.tasks.task_snapshot", return_value=snapshot):
        response = client.get("/device/v1/tasks/t1", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json()["status"] == "done"


# ── task list ────────────────────────────────────────────────────────────


def test_device_task_list_missing_device_id(client):
    response = client.get("/device/v1/tasks", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_device_task_list_for_device(client):
    tasks = [{"task_id": "t1"}]
    mock_store = MagicMock()
    mock_store.list_tasks_for_device.return_value = tasks
    with patch("device_gateway.store.task_store", mock_store):
        response = client.get(
            "/device/v1/tasks?device_id=dev-1&status=pending",
            headers={"Authorization": "Bearer test-key"},
        )
    assert response.status_code == 200
    assert response.json()["count"] == 1


# ── drawing history ──────────────────────────────────────────────────────


def test_device_drawing_history(client):
    artifact = MagicMock()
    artifact.task_id = "t1"
    artifact.artifact_type = "svg"
    artifact.content = "<svg/>"
    artifact.content_hash = "abc"
    artifact.created_at = "2026-01-01T00:00:00Z"
    with patch("device_artifacts.store.artifacts_for_device", return_value=[artifact]):
        response = client.get(
            "/device/v1/devices/dev-1/history",
            headers={"Authorization": "Bearer test-key"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["history"][0]["task_id"] == "t1"
