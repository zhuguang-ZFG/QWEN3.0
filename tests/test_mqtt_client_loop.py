"""Regression tests for device_gateway/mqtt_client.py event loop handling (P0-2)."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

import device_gateway.mqtt_client as mqtt_client


@pytest.fixture(autouse=True)
def _reset_mqtt_state():
    mqtt_client._mqtt_devices.clear()
    mqtt_client._main_loop = None
    yield
    mqtt_client._mqtt_devices.clear()
    mqtt_client._main_loop = None


def test_motion_event_without_running_loop_warns_and_drops(caplog):
    """If no main loop is stored and the callback thread has no running loop, the event is dropped with a warning."""
    mqtt_client._mqtt_devices["dev-1"] = MagicMock()  # type: ignore[assignment]
    payload = {
        "type": "motion_event",
        "device_id": "dev-1",
        "task_id": "task-1",
        "phase": "done",
    }

    with (
        caplog.at_level("WARNING"),
        patch("device_gateway.auth.validate_device_token", return_value=True),
        patch("routes.device_gateway_ws_handlers.handle_motion_event") as mock_handle,
    ):
        mqtt_client._handle_mqtt_message(
            MagicMock(), "device/dev-1/uplink", payload, json, time
        )

    mock_handle.assert_not_called()
    assert any("no running event loop" in m for m in caplog.messages), caplog.messages


def test_motion_event_with_main_loop_forwards_via_threadsafe():
    """When _main_loop is set, motion_event is forwarded using run_coroutine_threadsafe."""
    loop = MagicMock()
    loop.is_running.return_value = True
    mqtt_client._main_loop = loop  # type: ignore[assignment]
    mqtt_client._mqtt_devices["dev-1"] = MagicMock()  # type: ignore[assignment]
    payload = {
        "type": "motion_event",
        "device_id": "dev-1",
        "task_id": "task-1",
        "phase": "done",
    }

    with (
        patch("device_gateway.auth.validate_device_token", return_value=True),
        patch("routes.device_gateway_ws_handlers.handle_motion_event") as mock_handle,
        patch("asyncio.run_coroutine_threadsafe") as mock_run,
    ):
        mqtt_client._handle_mqtt_message(
            MagicMock(), "device/dev-1/uplink", payload, json, time
        )

    # Calling an async function returns a coroutine; the body is not executed.
    expected_message = {
        "type": "motion_event",
        "device_id": "dev-1",
        "session_id": None,
        "task_id": "task-1",
        "phase": "done",
        "progress": {},
        "request_id": None,
    }
    mock_handle.assert_called_once_with("dev-1", expected_message, None)
    mock_run.assert_called_once()
    assert mock_run.call_args[0][1] is loop
