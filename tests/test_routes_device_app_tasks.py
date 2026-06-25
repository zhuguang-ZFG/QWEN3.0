"""Tests for routes/device_app_tasks.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_app_tasks as tasks


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(tasks.router)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def account():
    return {"id": "acc-1", "phone": "12345678901", "role": "user"}


def _make_conn(rows=None, fetchone_sequence=None):
    conn = MagicMock()
    cursor = MagicMock()
    if rows is not None:
        cursor.fetchall.return_value = rows
        cursor.fetchone.return_value = rows[0] if rows else None
    elif fetchone_sequence is not None:
        cursor.fetchone.side_effect = fetchone_sequence
    else:
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None
    conn.execute.return_value = cursor
    return conn


def _ctx_manager(conn):
    class Ctx:
        def __enter__(self):
            return conn

        def __exit__(self, *args):
            return False

    return Ctx()


def _patch_conn(rows=None, fetchone_sequence=None):
    return patch.object(
        tasks, "connect", return_value=_ctx_manager(_make_conn(rows=rows, fetchone_sequence=fetchone_sequence))
    )


def _make_task_row(**overrides):
    return {
        "id": overrides.get("id", "task-1"),
        "device_id": overrides.get("device_id", "dev-1"),
        "account_id": overrides.get("account_id", "acc-1"),
        "intent": overrides.get("intent", "write_text"),
        "params": overrides.get("params", "{}"),
        "source": overrides.get("source", "api"),
        "status": overrides.get("status", "approved"),
        "progress": overrides.get("progress", 0),
        "error_msg": overrides.get("error_msg", ""),
        "member_id": overrides.get("member_id", ""),
        "created_at": overrides.get("created_at", "2024-01-01T00:00:00Z"),
        "started_at": overrides.get("started_at", ""),
        "completed_at": overrides.get("completed_at", ""),
    }


@pytest.fixture(autouse=True)
def _patch_deps(account):
    with (
        patch.object(tasks, "authorize", return_value=account),
        patch.object(tasks, "require_device_access", return_value=None),
        patch.object(tasks, "require_device_control", return_value=None),
        patch.object(tasks, "require_device_owner", return_value=None),
        patch.object(tasks.store_mod, "task_store", MagicMock()) as mock_store,
        patch.object(tasks, "create_and_route_task") as mock_create_route,
        patch.object(tasks, "project_to_motion_task_async") as mock_project,
        patch.object(tasks, "validate_capability_params", return_value=({}, None)),
        patch.object(tasks, "dispatch_or_enqueue", return_value={"sent": True, "queueDepth": 0}),
        patch.object(tasks, "task_snapshot", return_value=None),
        patch.object(tasks, "insert_task_row") as mock_insert,
        patch.object(tasks, "approve_task_row") as mock_approve,
        patch.object(tasks, "dispatch_approved_task") as mock_dispatch_approved,
        patch.object(tasks, "reject_task_row") as mock_reject,
        patch.object(tasks, "record_rejection"),
    ):
        mock_store.list_tasks_for_device.return_value = []
        mock_create_route.return_value = SimpleNamespace(
            task={"task_id": "task-1"},
            status="approved",
            sent=True,
            queue_depth=0,
        )
        mock_project.return_value = {
            "task_id": "task-1",
            "capability": "write_text",
            "params": {},
            "device_id": "dev-1",
            "workflow_state": "ready",
        }
        mock_insert.return_value = _make_task_row()
        mock_approve.return_value = (_make_task_row(status="approved"), {"task_id": "task-1"})
        mock_dispatch_approved.return_value = {"sent": True, "queueDepth": 0}
        mock_reject.return_value = _make_task_row(status="rejected")
        yield


def test_create_task_with_text_success(client, auth_header):
    response = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        json={"text": "draw a cat"},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert response.json()["taskId"] == "task-1"


def test_create_structured_task_success(client, auth_header):
    response = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        json={"capability": "write_text", "params": {"text": "hello"}, "source": "api"},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert response.json()["taskId"] == "task-1"


def test_create_structured_task_unsupported_capability(client, auth_header):
    with patch.object(tasks, "validate_capability_params", return_value=({}, "bad param")):
        response = client.post(
            "/device/v1/app/devices/dev-1/tasks",
            json={"capability": "write_text", "params": {"text": "hello"}, "source": "api"},
            headers=auth_header,
        )
    assert response.status_code == 400


def test_create_structured_task_invalid_source(client, auth_header):
    response = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        json={"capability": "write_text", "params": {}, "source": "bad"},
        headers=auth_header,
    )
    assert response.status_code == 400


def test_list_tasks_success(client, auth_header):
    with _patch_conn(rows=[_make_task_row()]):
        response = client.get("/device/v1/app/tasks?device_id=dev-1", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_get_task_from_snapshot_success(client, auth_header):
    with patch.object(
        tasks,
        "task_snapshot",
        return_value={"task": {"task_id": "task-1", "device_id": "dev-1"}, "status": "running"},
    ):
        response = client.get("/device/v1/app/tasks/task-1", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["taskId"] == "task-1"


def test_get_task_from_db_success(client, auth_header):
    with _patch_conn(rows=[_make_task_row()]):
        response = client.get("/device/v1/app/tasks/task-1", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["taskId"] == "task-1"


def test_get_task_not_found(client, auth_header):
    with _patch_conn(rows=[]):
        response = client.get("/device/v1/app/tasks/task-1", headers=auth_header)
    assert response.status_code == 404


def test_pending_voice_tasks_success(client, auth_header):
    with _patch_conn(rows=[_make_task_row(status="pending")]):
        response = client.post("/device/v1/app/devices/dev-1/voice-tasks/pending", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_approve_task_success(client, auth_header):
    response = client.post("/device/v1/app/tasks/task-1/approve", json={}, headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_reject_task_success(client, auth_header):
    response = client.post("/device/v1/app/tasks/task-1/reject", json={"reason": "no need"}, headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_routes_require_auth(client):
    with patch.object(tasks, "authorize", return_value=tasks.err(401, "Unauthorized", 401)):
        response = client.get("/device/v1/app/tasks?device_id=dev-1")
    assert response.status_code == 401
