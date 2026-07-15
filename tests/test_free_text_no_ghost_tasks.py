"""Tests: free-text insert-before-enqueue (HIGH residual fix)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_app_task_create as tasks_create
from routes import device_app_tasks as tasks


@pytest.fixture
def account():
    return {"id": "acc-1", "phone": "12345678901", "role": "user"}


def _make_task_row(**overrides):
    return {
        "id": overrides.get("id", "task-1"),
        "device_id": overrides.get("device_id", "dev-1"),
        "account_id": overrides.get("account_id", "acc-1"),
        "intent": overrides.get("intent", "write_text"),
        "params": overrides.get("params", "{}"),
        "source": overrides.get("source", "api"),
        "status": overrides.get("status", "pending"),
        "progress": overrides.get("progress", 0),
        "error_msg": overrides.get("error_msg", ""),
        "member_id": overrides.get("member_id", ""),
        "created_at": overrides.get("created_at", "2024-01-01T00:00:00Z"),
        "started_at": overrides.get("started_at", ""),
        "completed_at": overrides.get("completed_at", ""),
    }


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(tasks.router)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def _patch_common(account):
    with (
        patch.object(tasks, "authorize", return_value=account),
        patch.object(tasks, "require_device_control", return_value=None),
        patch.object(tasks, "check_key_limit", return_value=None),
        patch.object(tasks_create, "create_and_route_task") as mock_create_route,
        patch.object(tasks_create, "insert_task_row") as mock_insert,
        patch.object(tasks_create, "enqueue_pending_task", return_value=0) as mock_enqueue,
        patch.object(tasks_create, "mark_task_failed") as mock_mark_failed,
    ):
        from types import SimpleNamespace

        mock_create_route.return_value = SimpleNamespace(
            task={"task_id": "task-ft-1", "capability": "write_text", "params": {}},
            status="created",
            sent=False,
            queue_depth=0,
        )
        mock_insert.return_value = _make_task_row(id="task-ft-1", status="approved")
        yield {
            "create": mock_create_route,
            "insert": mock_insert,
            "enqueue": mock_enqueue,
            "mark_failed": mock_mark_failed,
        }


class TestFreeTextInsertBeforeEnqueue:
    def test_insert_failure_does_not_enqueue(self, client, auth_header, monkeypatch):
        order: list[str] = []

        async def create_only(request, *, enqueue: bool = True):
            from types import SimpleNamespace

            order.append(f"create:enqueue={enqueue}")
            if enqueue:
                order.append("enqueue_inside_route")
            return SimpleNamespace(
                task={"task_id": "task-ft-1", "capability": "write_text", "params": {}},
                status="queued_no_delivery" if enqueue else "created",
                sent=False,
                queue_depth=1 if enqueue else 0,
            )

        def failing_insert(*args, **kwargs):
            order.append("insert")
            raise RuntimeError("db down")

        def track_enqueue(device_id, task):
            order.append("enqueue")
            return 1

        monkeypatch.setattr(tasks_create, "create_and_route_task", create_only)
        monkeypatch.setattr(tasks_create, "insert_task_row", failing_insert)
        monkeypatch.setattr(tasks_create, "enqueue_pending_task", track_enqueue)
        response = client.post(
            "/device/v1/app/devices/dev-1/tasks",
            json={"text": "draw a circle"},
            headers=auth_header,
        )
        assert response.status_code == 500
        assert "enqueue" not in order and "enqueue_inside_route" not in order, order
        assert order == ["create:enqueue=False", "insert"], order

    def test_insert_before_enqueue_order(self, client, auth_header, monkeypatch):
        order: list[str] = []

        async def create_only(request, *, enqueue: bool = True):
            from types import SimpleNamespace

            order.append(f"create:enqueue={enqueue}")
            if enqueue:
                order.append("enqueue_inside_route")
            return SimpleNamespace(
                task={"task_id": "task-ft-2", "capability": "write_text", "params": {}},
                status="queued_no_delivery" if enqueue else "created",
                sent=False,
                queue_depth=1 if enqueue else 0,
            )

        def track_insert(*args, **kwargs):
            order.append("insert")
            return _make_task_row(id="task-ft-2", status="approved")

        def track_enqueue(device_id, task):
            order.append("enqueue")
            return 1

        monkeypatch.setattr(tasks_create, "create_and_route_task", create_only)
        monkeypatch.setattr(tasks_create, "insert_task_row", track_insert)
        monkeypatch.setattr(tasks_create, "enqueue_pending_task", track_enqueue)
        response = client.post(
            "/device/v1/app/devices/dev-1/tasks",
            json={"text": "write hello"},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert order == ["create:enqueue=False", "insert", "enqueue"], order
        body = response.json()
        assert body["taskId"] == "task-ft-2"
        assert body["dispatchStatus"] == "queued_no_delivery"
