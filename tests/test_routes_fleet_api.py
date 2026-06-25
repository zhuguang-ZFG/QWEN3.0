"""Tests for routes/fleet_api.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fleet.node_registry import NodeCapabilities, NodeRegistry
from fleet.task_dispatcher import TaskDispatcher
from routes import fleet_api as fleet_routes


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    fleet_routes.inject_state(admin_token="fleet-admin-token")
    yield
    fleet_routes.inject_state(admin_token="")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(fleet_routes.router)
    return TestClient(app)


@pytest.fixture
def registry_and_dispatcher():
    registry = NodeRegistry()
    dispatcher = TaskDispatcher()
    registry.register("node-1", capabilities=NodeCapabilities(shell=True))
    with (
        patch("fleet.node_registry.get_registry", return_value=registry),
        patch("fleet.task_dispatcher.get_dispatcher", return_value=dispatcher),
    ):
        yield registry, dispatcher


def _auth_header(token: str = "fleet-admin-token"):
    return {"Authorization": f"Bearer {token}"}


def test_missing_token_returns_503(client):
    fleet_routes.inject_state(admin_token="")
    response = client.post("/fleet/register", headers=_auth_header(""), json={"node_id": "n"})
    assert response.status_code == 503


def test_invalid_token_returns_401(client):
    response = client.post("/fleet/register", headers=_auth_header("bad"), json={"node_id": "n"})
    assert response.status_code == 401


def test_register_node(client, registry_and_dispatcher):
    response = client.post(
        "/fleet/register",
        headers=_auth_header(),
        json={"node_id": "node-2", "role": "worker", "gpu": True},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["node"]["node_id"] == "node-2"


def test_heartbeat_unknown_node(client, registry_and_dispatcher):
    response = client.post(
        "/fleet/heartbeat",
        headers=_auth_header(),
        json={"node_id": "missing", "load_avg": 0.5},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_heartbeat_known_node(client, registry_and_dispatcher):
    response = client.post(
        "/fleet/heartbeat",
        headers=_auth_header(),
        json={"node_id": "node-1", "load_avg": 0.5},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_list_nodes(client, registry_and_dispatcher):
    response = client.get("/fleet/nodes", headers=_auth_header())
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["nodes"][0]["node_id"] == "node-1"


def test_submit_task(client, registry_and_dispatcher):
    response = client.post(
        "/fleet/submit",
        headers=_auth_header(),
        json={"task_type": "shell", "command": "echo hi"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["task_id"].startswith("fleet-")


def test_poll_tasks_assigns_task(client, registry_and_dispatcher):
    registry, dispatcher = registry_and_dispatcher
    task = dispatcher.submit("shell", "echo hi")
    response = client.get("/fleet/poll/node-1", headers=_auth_header())
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["task"]["task_id"] == task.task_id


def test_poll_unregistered_node(client, registry_and_dispatcher):
    response = client.get("/fleet/poll/missing", headers=_auth_header())
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_complete_task(client, registry_and_dispatcher):
    registry, dispatcher = registry_and_dispatcher
    task = dispatcher.submit("shell", "echo hi")
    dispatcher.dispatch(registry)
    response = client.post(
        "/fleet/complete",
        headers=_auth_header(),
        json={"task_id": task.task_id, "result": "done", "error": ""},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert registry.get_node("node-1").tasks_completed == 1


def test_complete_task_error_marks_failed(client, registry_and_dispatcher):
    registry, dispatcher = registry_and_dispatcher
    task = dispatcher.submit("shell", "echo hi")
    dispatcher.dispatch(registry)
    response = client.post(
        "/fleet/complete",
        headers=_auth_header(),
        json={"task_id": task.task_id, "result": "", "error": "boom"},
    )
    assert response.status_code == 200
    assert registry.get_node("node-1").tasks_failed == 1


def test_complete_unknown_task(client, registry_and_dispatcher):
    response = client.post(
        "/fleet/complete",
        headers=_auth_header(),
        json={"task_id": "missing", "result": "done"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False
