"""Tests for device task Prometheus metrics."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import device_gateway.tasks as tasks_mod
from device_gateway.tasks import DeviceTaskRequest, create_and_route_task
from device_logic.gateway import build_gateway_task, dispatch_or_enqueue


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
        patch("device_gateway.tasks.enqueue_pending_task", return_value=1),
        patch("observability.prometheus_metrics.record_device_task_dispatched") as mock_dispatched,
        patch("observability.prometheus_metrics.set_device_tasks_pending") as mock_pending,
    ):
        result = await dispatch_or_enqueue("dev-1", sample_task)

    assert result["dispatchStatus"] == "queued"
    assert result["sent"] is False
    mock_dispatched.assert_called_once_with("home", "queued")
    mock_pending.assert_called()


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
        patch.object(tasks_mod, "enqueue_pending_task", return_value=1),
        patch("observability.prometheus_metrics.record_device_task_issued") as mock_issued,
        patch("observability.prometheus_metrics.record_device_task_dispatched") as mock_dispatched,
        patch("observability.prometheus_metrics.set_device_tasks_pending") as mock_pending,
    ):
        result = await create_and_route_task(request)

    assert result.status == "queued"
    mock_issued.assert_called_once_with("home", "api")
    mock_dispatched.assert_called_once_with("home", "queued")
    mock_pending.assert_called()
