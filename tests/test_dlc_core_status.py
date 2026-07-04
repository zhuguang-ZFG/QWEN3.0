"""Tests for dlc_core device status facade."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from dlc_core.device_status import get_device_status


@pytest.mark.asyncio
@patch("dlc_core.device_status.shadow_store")
@patch("dlc_core.device_status._build_device_status")
async def test_get_device_status_aggregates_runtime_state(mock_build_status, mock_shadow_store) -> None:
    mock_build_status.return_value = {
        "deviceId": "dev-1",
        "online": True,
        "working": True,
        "activeTaskId": "task-001",
        "firmwareVersion": "u8-3.9.0",
        "protocolVersion": "lima-device-v2",
        "connectedAt": "2026-07-04T09:00:00Z",
        "lastSeenAt": "2026-07-04T09:01:00Z",
    }
    mock_shadow_store.snapshot.return_value = {
        "device_id": "dev-1",
        "fw_rev": "u8-3.9.0",
        "last_motion_event": {"phase": "running"},
    }

    result = await get_device_status("dev-1")

    assert result == {
        "device_id": "dev-1",
        "online": True,
        "working": True,
        "active_task_id": "task-001",
        "firmware_version": "u8-3.9.0",
        "last_seen_at": "2026-07-04T09:01:00Z",
        "shadow": {
            "device_id": "dev-1",
            "fw_rev": "u8-3.9.0",
            "last_motion_event": {"phase": "running"},
        },
    }
    mock_build_status.assert_called_once_with("dev-1")
    mock_shadow_store.snapshot.assert_called_once_with("dev-1")


@pytest.mark.asyncio
@patch("dlc_core.device_status.shadow_store")
@patch("dlc_core.device_status._build_device_status")
async def test_get_device_status_uses_empty_shadow_when_missing(mock_build_status, mock_shadow_store) -> None:
    mock_build_status.return_value = {
        "deviceId": "dev-1",
        "online": False,
        "working": False,
        "activeTaskId": None,
        "firmwareVersion": None,
        "protocolVersion": None,
        "connectedAt": None,
        "lastSeenAt": None,
    }
    mock_shadow_store.snapshot.return_value = None

    result = await get_device_status("dev-1")

    assert result["online"] is False
    assert result["working"] is False
    assert result["active_task_id"] is None
    assert result["firmware_version"] is None
    assert result["last_seen_at"] is None
    assert result["shadow"] == {}
