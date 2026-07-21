"""M1: device /device/v1/ws hello + online motion_task push after enqueue."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.sessions import registry
from device_gateway.tasks import (
    DeviceTaskRequest,
    create_and_route_task,
    install_task_store_for_tests,
    reset_tasks_for_tests,
)
from device_ws_ticket import issue as issue_ticket
from device_ws_ticket import reset as reset_tickets
from routes.device_ws import router as device_ws_router


@pytest.fixture
def app_client(monkeypatch):
    install_task_store_for_tests()
    registry.clear()
    reset_tickets()
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=secret-token-1")
    # Reload configured tokens from env
    from device_gateway import auth as device_auth

    monkeypatch.setattr(
        device_auth,
        "configured_device_tokens",
        lambda: {"dev-1": "secret-token-1"},
    )
    app = FastAPI()
    app.include_router(device_ws_router)
    return TestClient(app)


def test_ws_ticket_requires_valid_token(app_client):
    bad = app_client.post(
        "/device/v1/ws/ticket",
        headers={"Authorization": "Bearer wrong"},
        json={"device_id": "dev-1"},
    )
    assert bad.status_code == 401
    ok = app_client.post(
        "/device/v1/ws/ticket",
        headers={"Authorization": "Bearer secret-token-1"},
        json={"device_id": "dev-1"},
    )
    assert ok.status_code == 200
    assert ok.json()["ticket"]
    assert ok.json()["expires_in"] == 30


@pytest.mark.asyncio
async def test_create_and_route_sent_when_session_online(app_client, monkeypatch):
    install_task_store_for_tests()
    registry.clear()
    reset_tickets()

    sent: list[dict] = []

    class _Ws:
        async def send_json(self, payload):
            sent.append(payload)

    from device_gateway.sessions import DeviceSession

    session = DeviceSession(device_id="dev-1", websocket=_Ws())
    registry.register(session)

    result = await create_and_route_task(
        DeviceTaskRequest(
            device_id="dev-1",
            text="home",
            source="test",
            entrypoint="test",
            voice_task={"capability": "home", "params": {}, "source": "test"},
        )
    )
    assert result.status == "sent"
    assert result.sent is True
    assert any(m.get("type") == "motion_task" and m.get("capability") == "home" for m in sent)


def test_hello_and_drain_on_connect(app_client, monkeypatch):
    install_task_store_for_tests()
    registry.clear()
    reset_tickets()
    monkeypatch.setattr(
        "device_gateway.auth.validate_device_token",
        lambda device_id, token: device_id == "dev-1" and token == "secret-token-1",
    )

    # Pre-enqueue a task while offline
    from device_gateway.tasks import enqueue_pending_task

    task = {
        "type": "motion_task",
        "task_id": "task-pre-1",
        "device_id": "dev-1",
        "capability": "home",
        "params": {"source_capability": "home"},
        "source": "test",
    }
    from device_gateway.store import task_store

    task_store.create_task_state(task, status="created")
    enqueue_pending_task("dev-1", task)

    ticket = issue_ticket("dev-1", "secret-token-1")
    with app_client.websocket_connect(f"/device/v1/ws?ticket={ticket}") as ws:
        ws.send_text(json.dumps({"type": "hello", "device_id": "dev-1", "fw_rev": "1.0.0"}))
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"
        assert ack["device_id"] == "dev-1"
        # Drain should push the pre-queued home task
        pushed = ws.receive_json()
        assert pushed["type"] == "motion_task"
        assert pushed["task_id"] == "task-pre-1"
        assert pushed["capability"] == "home"


@pytest.mark.asyncio
async def test_offline_create_returns_queued_no_delivery():
    install_task_store_for_tests()
    reset_tasks_for_tests()
    registry.clear()

    result = await create_and_route_task(
        DeviceTaskRequest(
            device_id="dev-offline",
            text="home",
            voice_task={"capability": "home", "params": {}, "source": "test"},
        )
    )
    assert result.status == "queued_no_delivery"
    assert result.sent is False
