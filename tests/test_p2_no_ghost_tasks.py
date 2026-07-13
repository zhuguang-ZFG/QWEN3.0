"""Tests: no ghost tasks — insert before dispatch (P2 fix-q)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_app_task_create as tasks_create
from routes import device_app_tasks as tasks
from routes import device_app_task_extras as extras


@pytest.fixture
def account():
    return {"id": "acc-1", "phone": "12345678901", "role": "user"}


def _make_task_row(**overrides):
    row = {
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
    return row


# ── Structured-task endpoint helpers ─────────────────────────────


@pytest.fixture
def struct_client():
    app = FastAPI()
    app.include_router(tasks.router)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def _patch_common(account):
    """Patch authorisation, DB connect & building for structured-task tests."""
    with (
        patch.object(tasks, "authorize", return_value=account),
        patch.object(tasks, "require_device_access", return_value=None),
        patch.object(tasks, "require_device_control", return_value=None),
        patch.object(tasks, "require_device_owner", return_value=None),
        patch.object(tasks.store_mod, "task_store", MagicMock()),
        patch.object(tasks, "create_and_route_task") as mock_create_route,
        patch.object(tasks_create, "project_to_motion_task_async") as mock_project,
        patch.object(tasks_create, "validate_capability_params", return_value=({}, None)),
        patch.object(tasks_create, "dispatch_or_enqueue") as mock_dispatch,
        patch.object(tasks_create, "insert_task_row") as mock_insert,
        patch.object(tasks_create, "mark_task_failed") as mock_mark_failed,
    ):
        mock_create_route.return_value = MagicMock(
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
        mock_dispatch.return_value = {"sent": False, "queueDepth": 0}
        mock_insert.return_value = _make_task_row()
        yield


# ── Structured-task: insert fails → dispatch NOT called ──────────


class TestStructuredInsertFailurePreventsDispatch:
    """insert_task_row raises → route returns 5xx, dispatch never called."""

    def test_insert_exception_returns_500(self, struct_client, auth_header):
        with patch.object(tasks_create, "insert_task_row", side_effect=RuntimeError("db down")):
            response = struct_client.post(
                "/device/v1/app/devices/dev-1/tasks",
                json={"capability": "write_text", "params": {"text": "hi"}, "source": "api"},
                headers=auth_header,
            )
        assert response.status_code == 500

    def test_insert_exception_dispatch_not_called(self, struct_client, auth_header, monkeypatch):
        call_count = 0

        def failing_insert(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("db down")

        async def count_dispatch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {"sent": False, "queueDepth": 0}

        monkeypatch.setattr(tasks_create, "insert_task_row", failing_insert)
        monkeypatch.setattr(tasks_create, "_dispatch_or_wait", count_dispatch)
        struct_client.post(
            "/device/v1/app/devices/dev-1/tasks",
            json={"capability": "write_text", "params": {"text": "hi"}, "source": "api"},
            headers=auth_header,
        )
        # insert_task_row was called once, _dispatch_or_wait never called
        assert call_count == 1, f"expected 1 call (insert only), got {call_count}"


# ── Structured-task: dispatch fails → mark_task_failed called ────


class TestStructuredDispatchFailureMarksFailed:
    """dispatch_or_enqueue raises → mark_task_failed called, row status=failed."""

    def test_dispatch_exception_calls_mark_failed(self, struct_client, auth_header):
        with patch.object(tasks_create, "dispatch_or_enqueue", side_effect=RuntimeError("gw down")):
            response = struct_client.post(
                "/device/v1/app/devices/dev-1/tasks",
                json={"capability": "write_text", "params": {"text": "hi"}, "source": "api"},
                headers=auth_header,
            )
        assert response.status_code == 500
        tasks_create.mark_task_failed.assert_called_once_with("task-1", "dispatch failed")

    def test_dispatch_exception_insert_was_called(self, struct_client, auth_header, monkeypatch):
        """Verify insert was attempted before dispatch failure."""
        insert_called = False

        def tracking_insert(*args, **kwargs):
            nonlocal insert_called
            insert_called = True
            return _make_task_row()

        monkeypatch.setattr(tasks_create, "insert_task_row", tracking_insert)
        with patch.object(tasks_create, "dispatch_or_enqueue", side_effect=RuntimeError("gw down")):
            struct_client.post(
                "/device/v1/app/devices/dev-1/tasks",
                json={"capability": "write_text", "params": {"text": "hi"}, "source": "api"},
                headers=auth_header,
            )
        assert insert_called, "insert_task_row should have been called before dispatch"


# ── Batch-task endpoint helpers ──────────────────────────────────


@pytest.fixture
def batch_client():
    app = FastAPI()
    app.include_router(extras.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _patch_batch_deps():
    """Patch auth & building for batch-task tests."""
    with (
        patch.object(extras, "authorize", return_value={"id": "acc-1"}),
        patch.object(extras, "require_device_control", return_value=None),
        patch.object(extras, "check_key_limit", return_value=None),
        patch.object(extras, "_build_app_gateway_task") as mock_build,
        patch.object(extras, "_dispatch_or_wait") as mock_dispatch,
        patch.object(extras, "insert_task_row") as mock_insert,
        patch.object(extras, "mark_task_failed") as mock_mark_failed,
    ):
        mock_build.return_value = (
            {
                "task_id": "task-b-1",
                "capability": "write_text",
                "params": {},
                "device_id": "dev-1",
                "workflow_state": "ready",
            },
            None,
        )
        mock_dispatch.return_value = ({"sent": False, "queueDepth": 0}, "approved")
        mock_insert.return_value = _make_task_row(id="task-b-1")
        yield


# ── Batch: insert fails → dispatch NOT called ────────────────────


class TestBatchInsertFailurePreventsDispatch:
    """Batch: insert_task_row raises → individual task fails, dispatch not called."""

    def test_batch_insert_exception_returns_failed_item(self, batch_client, auth_header):
        """When insert raises, the item shows as failed with error."""
        with patch.object(extras, "insert_task_row", side_effect=RuntimeError("db down")):
            response = batch_client.post(
                "/device/v1/app/devices/dev-1/batch-tasks",
                json={"tasks": [{"capability": "write_text", "params": {"text": "hi"}}]},
                headers=auth_header,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["tasks"][0]["status"] == "failed"
        assert "error" in data["tasks"][0]

    def test_batch_insert_exception_dispatch_not_called(self, batch_client, auth_header, monkeypatch):
        """Verify _dispatch_or_wait is never called when insert fails."""
        dispatch_call_count = 0

        async def count_dispatch(*args, **kwargs):
            nonlocal dispatch_call_count
            dispatch_call_count += 1
            return ({"sent": False, "queueDepth": 0}, "approved")

        monkeypatch.setattr(extras, "_dispatch_or_wait", count_dispatch)
        with patch.object(extras, "insert_task_row", side_effect=RuntimeError("db down")):
            batch_client.post(
                "/device/v1/app/devices/dev-1/batch-tasks",
                json={"tasks": [{"capability": "write_text", "params": {"text": "hi"}}]},
                headers=auth_header,
            )
        assert dispatch_call_count == 0, "_dispatch_or_wait should NOT be called when insert fails"


# ── Batch: dispatch fails → mark_task_failed called ──────────────


class TestBatchDispatchFailureMarksFailed:
    """Batch: dispatch fails → mark_task_failed called, item shows as failed."""

    def test_batch_dispatch_exception_calls_mark_failed(self, batch_client, auth_header):
        with patch.object(extras, "_dispatch_or_wait", side_effect=RuntimeError("gw down")):
            response = batch_client.post(
                "/device/v1/app/devices/dev-1/batch-tasks",
                json={"tasks": [{"capability": "write_text", "params": {"text": "hi"}}]},
                headers=auth_header,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["tasks"][0]["status"] == "failed"
        extras.mark_task_failed.assert_called_once_with("task-b-1", "dispatch failed")
