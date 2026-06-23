"""Tests for routes/ws_task_helpers.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routes import ws_task_helpers as wth


@pytest.fixture
def session():
    s = MagicMock()
    s.send_json = AsyncMock()
    return s


@pytest.mark.asyncio
async def test_send_recovery_ack_home(session):
    with patch("routes.ws_task_helpers.ack_frame", return_value={"type": "ack"}) as mock_ack:
        await wth.send_recovery_ack(
            session,
            device_id="dev-1",
            message={"task_id": "task-1"},
            request_id="req-1",
            recovery_result={"action": "home"},
        )
    mock_ack.assert_called_once_with(
        "home_command",
        "dev-1",
        task_id="task-1",
        reason="recovery_action_home",
        request_id="req-1",
    )
    session.send_json.assert_awaited_once_with({"type": "ack"})


@pytest.mark.asyncio
async def test_send_recovery_ack_retry(session):
    with patch("routes.ws_task_helpers.ack_frame", return_value={"type": "ack"}) as mock_ack, patch(
        "routes.ws_task_helpers.mark_task_dispatched"
    ) as mock_mark, patch("routes.ws_task_helpers.remove_pending_task") as mock_remove:
        retry_task = {"task_id": "task-2"}
        await wth.send_recovery_ack(
            session,
            device_id="dev-1",
            message={"task_id": "task-1"},
            request_id="req-1",
            recovery_result={"action": "retry", "task": retry_task, "attempt": 3},
        )
    mock_ack.assert_called_once_with(
        "motion_task_retry",
        "dev-1",
        task_id="task-1",
        task=retry_task,
        attempt=3,
        request_id="req-1",
    )
    session.mark_task_dispatched.assert_called_once_with(retry_task)
    mock_mark.assert_called_once_with("task-2")
    mock_remove.assert_called_once_with("dev-1", "task-2")


@pytest.mark.asyncio
async def test_send_recovery_ack_retry_without_task(session):
    with patch("routes.ws_task_helpers.ack_frame", return_value={"type": "ack"}) as mock_ack:
        await wth.send_recovery_ack(
            session,
            device_id="dev-1",
            message={"task_id": "task-1"},
            request_id="req-1",
            recovery_result={"action": "retry"},
        )
    # No retry frame should be sent when task is missing.
    mock_ack.assert_not_called()
    session.send_json.assert_not_called()


def test_record_outcome_ledger_success():
    with patch("session_memory.outcome_ledger.record") as mock_record:
        wth.record_outcome_ledger(
            device_id="dev-1",
            message={"task_id": "task-1", "capability": "move"},
            phase="done",
        )
    mock_record.assert_called_once()
    call_kwargs = mock_record.call_args.kwargs
    assert call_kwargs["outcome"] == "success"
    assert call_kwargs["task_id"] == "task-1"


def test_record_outcome_ledger_failure():
    with patch("session_memory.outcome_ledger.record") as mock_record:
        wth.record_outcome_ledger(
            device_id="dev-1",
            message={"task_id": "task-1", "source_capability": "grab"},
            phase="failed",
        )
    assert mock_record.call_args.kwargs["outcome"] == "failure"
    assert "failed: grab" in mock_record.call_args.kwargs["summary"]


def test_record_outcome_ledger_swallows_exception():
    with patch("session_memory.outcome_ledger.record", side_effect=RuntimeError("boom")):
        # Should not raise.
        wth.record_outcome_ledger(
            device_id="dev-1",
            message={"task_id": "task-1"},
            phase="done",
        )
