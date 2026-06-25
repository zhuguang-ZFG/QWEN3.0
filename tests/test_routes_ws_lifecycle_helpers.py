"""Tests for routes/ws_lifecycle_helpers.py."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from device_workflow.state import TaskState, WorkflowTransitionError
from routes import ws_lifecycle_helpers as ws_lh


@pytest.fixture
def session():
    s = MagicMock()
    s.device_id = "dev-1"
    s.inflight_tasks = ["t-existing"]
    return s


@patch.object(ws_lh.workflow, "get_state")
@patch.object(ws_lh.workflow, "advance")
@patch.object(ws_lh.ledger_store, "append_event")
def test_reattach_tasks_dispatches_new_and_recover(mock_append, mock_advance, mock_get_state, session):
    mock_get_state.return_value = TaskState.DISPATCHED
    tasks = [
        {"task_id": "t-new", "capability": "move"},
        {"task_id": "t-existing", "capability": "move"},  # duplicate, skipped
    ]
    ws_lh.reattach_tasks(session, tasks)

    session.mark_task_dispatched.assert_called_once_with({"task_id": "t-new", "capability": "move"})
    mock_append.assert_called_once()
    event = mock_append.call_args.args[0]
    assert event.event_type == "motion_event"
    assert event.task_id == "t-new"
    assert event.device_id == "dev-1"

    # DISPATCHED -> RUNNING -> RECOVERING -> RUNNING
    assert mock_advance.call_count == 3


@patch.object(ws_lh.workflow, "get_state")
@patch.object(ws_lh.workflow, "advance")
@patch.object(ws_lh.ledger_store, "append_event")
def test_reattach_tasks_running_state_recovery(mock_append, mock_advance, mock_get_state, session):
    mock_get_state.return_value = TaskState.RUNNING
    ws_lh.reattach_tasks(session, [{"task_id": "t2"}])
    # RUNNING -> RECOVERING -> RUNNING
    assert mock_advance.call_count == 2


@patch.object(ws_lh.workflow, "get_state")
@patch.object(ws_lh.workflow, "advance")
@patch.object(ws_lh.ledger_store, "append_event")
def test_reattach_tasks_logs_transition_error(mock_append, mock_advance, mock_get_state, session, caplog):
    mock_get_state.return_value = TaskState.RUNNING
    mock_advance.side_effect = WorkflowTransitionError("invalid transition")
    with caplog.at_level(logging.DEBUG):
        ws_lh.reattach_tasks(session, [{"task_id": "t3"}])
    # Should not raise; logs debug
    assert any("workflow reconnect recovery skipped" in rec.message for rec in caplog.records)
