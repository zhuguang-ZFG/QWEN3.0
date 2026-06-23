"""Tests for routes/device_gateway_helpers.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from routes import device_gateway_helpers as helpers


@pytest.mark.asyncio
async def test_start_device_gateway_runtime():
    with (
        patch.object(helpers, "configure_task_store_from_env") as mock_task,
        patch.object(helpers, "configure_memory_store_from_env") as mock_mem,
        patch.object(helpers, "configure_ledger_store_from_env") as mock_led,
        patch.object(helpers, "configure_notifier_from_env") as mock_not,
        patch.object(helpers, "start_task_notifier") as mock_start,
    ):
        await helpers.start_device_gateway_runtime()
    mock_task.assert_called_once()
    mock_mem.assert_called_once()
    mock_led.assert_called_once()
    mock_not.assert_called_once()
    mock_start.assert_called_once_with(helpers.notify_local_session_task_available)


@pytest.mark.asyncio
async def test_stop_device_gateway_runtime():
    with patch.object(helpers, "stop_task_notifier") as mock_stop:
        await helpers.stop_device_gateway_runtime()
    mock_stop.assert_called_once()


def test_record_device_task_evidence():
    mock_record = MagicMock()
    with patch("observability.capability_evidence.record_evidence_safe", mock_record):
        helpers._record_device_task_evidence(
            device_id="dev-1",
            task={"task_id": "t1", "request_id": "r1"},
            status="queued",
            request_id="r1",
        )
    mock_record.assert_called_once()
    kwargs = mock_record.call_args.kwargs
    assert kwargs["loop"] == "device_gateway"
    assert kwargs["device_id"] == "dev-1"
    assert kwargs["status"] == "queued"


def test_reset_for_tests():
    with (
        patch.object(helpers.registry, "clear") as mock_clear,
        patch.object(helpers.shadow_store, "reset") as mock_shadow_reset,
        patch.object(helpers, "reset_tasks_for_tests") as mock_reset_tasks,
    ):
        helpers._reset_for_tests()
    mock_clear.assert_called_once()
    mock_shadow_reset.assert_called_once()
    mock_reset_tasks.assert_called_once()
