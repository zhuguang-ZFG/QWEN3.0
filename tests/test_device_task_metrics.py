"""Tests for device task Prometheus metrics and retry boundary."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import device_gateway.tasks as tasks_mod
import device_logic.gateway as gw_mod
import routes.device_gateway_dispatch as dispatch_mod
from device_gateway.tasks import DeviceTaskRequest, create_and_route_task
from device_logic.gateway import build_gateway_task, dispatch_or_enqueue
from routes.device_gateway_dispatch import MAX_TASK_RETRIES, requeue_session_outstanding


@pytest.fixture
def sample_task():
    return {
        "task_id": "task-abc123",
        "device_id": "dev-1",
        "capability": "home",
        "source": "voice",
        "params": {},
    }


def test_build_gateway_task_records_issued():
    with patch("observability.prometheus_metrics.record_device_task_issued") as mock_issued:
        task, error = build_gateway_task("dev-1", "home", {}, source="voice", request_id="")

    assert error is None
    assert task is not None
    mock_issued.assert_called_once_with("home", "voice")


@pytest.mark.asyncio
async def test_dispatch_or_enqueue_records_queued(sample_task):
    with (
        patch("device_gateway.sessions.registry.get", return_value=None),
        patch("device_gateway.tasks.enqueue_pending_task", return_value=1),
        patch("routes.device_gateway_dispatch.publish_task_available_safe", new=AsyncMock()),
        patch("observability.prometheus_metrics.record_device_task_dispatched") as mock_dispatched,
        patch("observability.prometheus_metrics.set_device_tasks_pending") as mock_pending,
    ):
        result = await dispatch_or_enqueue("dev-1", sample_task)

    assert result["dispatchStatus"] == "queued"
    mock_dispatched.assert_called_once_with("home", "queued")
    mock_pending.assert_called()


@pytest.mark.asyncio
async def test_dispatch_or_enqueue_records_sent(sample_task):
    session = MagicMock()
    with (
        patch("device_gateway.sessions.registry.get", return_value=session),
        patch("routes.device_gateway_dispatch.dispatch_task_to_session", return_value=True),
        patch("observability.prometheus_metrics.record_device_task_dispatched") as mock_dispatched,
    ):
        result = await dispatch_or_enqueue("dev-1", sample_task)

    assert result["dispatchStatus"] == "sent"
    mock_dispatched.assert_not_called()


@pytest.mark.asyncio
async def test_create_and_route_task_records_created_and_queued():
    task = {
        "task_id": "task-xyz",
        "device_id": "dev-1",
        "capability": "home",
        "source": "api",
        "params": {},
    }
    request = DeviceTaskRequest(device_id="dev-1", text="go home", request_id="r1", source="api")
    with (
        patch.object(tasks_mod, "create_task_from_transcript_async", return_value=task),
        patch("device_gateway.sessions.registry.get", return_value=None),
        patch.object(tasks_mod, "enqueue_pending_task", return_value=1),
        patch("routes.device_gateway_dispatch.publish_task_available_safe", new=AsyncMock()),
        patch("observability.prometheus_metrics.record_device_task_issued") as mock_issued,
        patch("observability.prometheus_metrics.record_device_task_dispatched") as mock_dispatched,
        patch("observability.prometheus_metrics.set_device_tasks_pending") as mock_pending,
    ):
        result = await create_and_route_task(request)

    assert result.status == "queued"
    mock_issued.assert_called_once_with("home", "api")
    mock_dispatched.assert_called_once_with("home", "queued")
    mock_pending.assert_called()


def test_requeue_session_outstanding_respects_max_retries(sample_task):
    session = MagicMock()
    session.device_id = "dev-1"
    session.take_outstanding_tasks.return_value = [sample_task]

    retry_counts = {sample_task["task_id"]: 0}

    def _increment(task_id: str) -> int:
        retry_counts[task_id] = retry_counts.get(task_id, 0) + 1
        return retry_counts[task_id]

    with (
        patch.object(dispatch_mod, "task_store") as store_mock,
        patch("observability.prometheus_metrics.record_device_task_retry") as mock_retry,
        patch("observability.prometheus_metrics.record_device_task_dead_letter") as mock_dead,
        patch.object(dispatch_mod, "requeue_pending_tasks") as mock_requeue,
    ):
        store_mock.increment_retry_count.side_effect = _increment
        store_mock.abandon_processing_task.return_value = True

        # First requeue is within budget.
        requeue_session_outstanding(session)
        assert mock_requeue.call_count == 1
        mock_retry.assert_called_with("home")

        # After enough retries the task is abandoned, not requeued.
        for _ in range(MAX_TASK_RETRIES):
            requeue_session_outstanding(session)

        assert store_mock.abandon_processing_task.call_count == 1
        mock_dead.assert_called_once_with("home")
