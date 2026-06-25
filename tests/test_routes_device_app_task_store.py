"""Tests for routes/device_app_task_store.py helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from routes import device_app_task_store as store


@pytest.fixture
def account():
    return {"id": "acc-1", "role": "user"}


@pytest.fixture
def task():
    return {"task_id": "task-1", "app_capability": "write_text", "capability": "write_text", "params": {}}


def _make_conn(row=None, rows=None, fetchone_sequence=None):
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_sequence is not None:
        cursor.fetchone.side_effect = fetchone_sequence
    else:
        cursor.fetchone.return_value = row
    cursor.fetchall.return_value = rows or []
    conn.execute.return_value = cursor
    return conn


def _patch_conn_sequence(sequence):
    return patch.object(store, "connect", return_value=_ctx_manager(_make_conn(fetchone_sequence=sequence)))


def _ctx_manager(conn):
    class Ctx:
        def __enter__(self):
            return conn

        def __exit__(self, *args):
            return False

    return Ctx()


def _patch_conn(row=None, rows=None):
    return patch.object(store, "connect", return_value=_ctx_manager(_make_conn(row=row, rows=rows)))


@pytest.fixture(autouse=True)
def _patch_deps():
    with (
        patch.object(store, "json_params", return_value='{"requestId": "req-1"}'),
        patch.object(store, "task_snapshot", return_value={"task": {"task_id": "task-1"}}),
        patch.object(store, "record_motion_event"),
        patch.object(store.workflow, "get_state", return_value=store.TaskState.WAITING_APPROVAL),
        patch.object(store.workflow, "advance"),
        patch.object(store, "dispatch_or_enqueue", return_value={"sent": True, "queueDepth": 0}) as mock_dispatch,
        patch.object(store, "require_device_owner", return_value=None),
    ):
        yield


def test_insert_task_row(account, task):
    row = {
        "id": "task-1",
        "device_id": "dev-1",
        "account_id": "acc-1",
        "intent": "write_text",
        "params": '{"requestId": "req-1"}',
        "source": "api",
        "status": "approved",
    }
    with _patch_conn(row=row):
        result = store.insert_task_row("dev-1", account, task, "api", "approved", {"requestId": "req-1"}, {})
    assert result["id"] == "task-1"


def test_approve_task_row_success(account):
    row = {"id": "task-1", "device_id": "dev-1", "status": "pending"}
    updated = {"id": "task-1", "device_id": "dev-1", "status": "approved"}
    with _patch_conn_sequence([row, updated]):
        result, task = store.approve_task_row("task-1", account)
    assert isinstance(task, dict)
    assert result["status"] == "approved"


def test_approve_task_row_not_found(account):
    with _patch_conn(row=None):
        result, task = store.approve_task_row("task-1", account)
    assert result.status_code == 404
    assert task is None


def test_approve_task_row_not_pending(account):
    row = {"id": "task-1", "device_id": "dev-1", "status": "approved"}
    with _patch_conn(row=row):
        result, task = store.approve_task_row("task-1", account)
    assert result.status_code == 400
    assert task is None


@pytest.mark.asyncio
async def test_dispatch_approved_task_dispatches():
    task = {"task_id": "task-1", "workflow_state": "ready"}
    result = await store.dispatch_approved_task("task-1", "dev-1", task)
    assert result["sent"] is True


@pytest.mark.asyncio
async def test_dispatch_approved_task_no_task():
    result = await store.dispatch_approved_task("task-1", "dev-1", None)
    assert result["sent"] is False


def test_reject_task_row_success(account):
    row = {"id": "task-1", "device_id": "dev-1", "status": "pending"}
    updated = {"id": "task-1", "device_id": "dev-1", "status": "rejected"}
    with _patch_conn_sequence([row, updated]):
        result = store.reject_task_row("task-1", account, "no need")
    assert result["status"] == "rejected"


def test_reject_task_row_not_found(account):
    with _patch_conn(row=None):
        result = store.reject_task_row("task-1", account, "no need")
    assert result.status_code == 404


def test_record_rejection():
    store.record_rejection("task-1", "dev-1", "no need")
    store.record_motion_event.assert_called_once()
