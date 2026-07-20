"""Status WS task terminal event mapping (completed / failed / unknown)."""

from __future__ import annotations

import logging
import time

import pytest

from device_app_helpers import client as make_client
from device_app_helpers import seed_account_and_device, seed_binding, token

_POLL_INTERVAL = 0.05


def _auth_query(account_id: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token(account_id)}"}


def _receive_event(websocket, event_name: str, *, timeout: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = websocket.receive_json()
        if message.get("event") == event_name:
            return message
    raise AssertionError(f"timed out waiting for event={event_name!r}")


def _task_payload(task_id: str = "task-001") -> dict:
    return {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": "dev-1",
        "capability": "run_path",
        "source": "voice",
        "params": {"path": [{"x": 0, "y": 0, "z": 0}]},
        "request_id": "req-001",
    }


def test_device_status_ws_task_completed_transition(tmp_path, monkeypatch):
    client, store = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr("routes.device_app_status_ws._POLL_INTERVAL", _POLL_INTERVAL)
    seed_account_and_device()
    seed_binding()

    with client.websocket_connect("/device/v1/app/devices/dev-1/ws", params=_auth_query("a-owner")) as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["event"] == "status_snapshot"
        assert snapshot["payload"]["activeTaskId"] is None

        store.create_task_state(_task_payload(), status="running")
        started = _receive_event(websocket, "task_started")
        assert started["payload"]["taskId"] == "task-001"

        store.record_motion_event(
            {"type": "motion_event", "device_id": "dev-1", "task_id": "task-001", "phase": "done"}
        )
        completed = _receive_event(websocket, "task_completed")
        assert completed["payload"]["taskId"] == "task-001"


def test_device_status_ws_task_failed_transition(tmp_path, monkeypatch):
    client, store = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr("routes.device_app_status_ws._POLL_INTERVAL", _POLL_INTERVAL)
    seed_account_and_device()
    seed_binding()

    with client.websocket_connect("/device/v1/app/devices/dev-1/ws", params=_auth_query("a-owner")) as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["event"] == "status_snapshot"
        assert snapshot["payload"]["activeTaskId"] is None

        store.create_task_state(_task_payload("task-fail"), status="running")
        started = _receive_event(websocket, "task_started")
        assert started["payload"]["taskId"] == "task-fail"

        store.record_motion_event(
            {"type": "motion_event", "device_id": "dev-1", "task_id": "task-fail", "phase": "failed"}
        )
        failed = _receive_event(websocket, "task_failed")
        assert failed["payload"]["taskId"] == "task-fail"


def test_device_status_ws_task_progress_event(tmp_path, monkeypatch):
    client, store = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr("routes.device_app_status_ws._POLL_INTERVAL", _POLL_INTERVAL)
    seed_account_and_device()
    seed_binding()

    with client.websocket_connect("/device/v1/app/devices/dev-1/ws", params=_auth_query("a-owner")) as websocket:
        assert websocket.receive_json()["event"] == "status_snapshot"
        store.create_task_state(_task_payload("task-prog"), status="running")
        assert _receive_event(websocket, "task_started")["payload"]["taskId"] == "task-prog"
        store.record_motion_event(
            {
                "type": "motion_event",
                "device_id": "dev-1",
                "task_id": "task-prog",
                "phase": "running",
                "progress": 42,
            }
        )
        progress = _receive_event(websocket, "task_progress")
        assert progress["payload"]["taskId"] == "task-prog"
        assert progress["payload"]["progress"] == 42


def test_device_status_ws_firmware_update_event(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr("routes.device_app_status_ws._POLL_INTERVAL", _POLL_INTERVAL)
    seed_account_and_device()
    seed_binding()

    states = {"fw": "1.0.0", "online": True}

    def _status(device_id: str) -> dict:
        fw = states["fw"] if states["online"] else None
        return {
            "deviceId": device_id,
            "online": states["online"],
            "connectedAt": "t0" if states["online"] else None,
            "working": False,
            "activeTaskId": None,
            "firmwareVersion": fw,
            "protocolVersion": "1" if states["online"] else None,
            "lastSeenAt": "t0" if states["online"] else None,
        }

    monkeypatch.setattr("routes.device_app_status_ws._build_device_status", _status)

    with client.websocket_connect("/device/v1/app/devices/dev-1/ws", params=_auth_query("a-owner")) as websocket:
        snap = websocket.receive_json()
        assert snap["event"] == "status_snapshot"
        assert snap["payload"]["firmwareVersion"] == "1.0.0"
        assert "_taskProgress" not in snap["payload"]
        states["fw"] = "1.1.0"
        fw_evt = _receive_event(websocket, "firmware_update")
        assert fw_evt["payload"]["firmwareVersion"] == "1.1.0"
        assert fw_evt["payload"]["previousFirmwareVersion"] == "1.0.0"


def test_device_status_ws_reconnect_same_fw_no_firmware_update(tmp_path, monkeypatch):
    """Offline clears firmwareVersion; coming back with same rev must not emit OTA."""
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr("routes.device_app_status_ws._POLL_INTERVAL", _POLL_INTERVAL)
    seed_account_and_device()
    seed_binding()

    states = {"fw": "1.0.0", "online": True}

    def _status(device_id: str) -> dict:
        online = states["online"]
        return {
            "deviceId": device_id,
            "online": online,
            "connectedAt": "t0" if online else None,
            "working": False,
            "activeTaskId": None,
            "firmwareVersion": states["fw"] if online else None,
            "protocolVersion": "1" if online else None,
            "lastSeenAt": "t0" if online else None,
        }

    monkeypatch.setattr("routes.device_app_status_ws._build_device_status", _status)

    with client.websocket_connect("/device/v1/app/devices/dev-1/ws", params=_auth_query("a-owner")) as websocket:
        assert websocket.receive_json()["event"] == "status_snapshot"
        states["online"] = False
        offline = _receive_event(websocket, "device_offline")
        assert offline["event"] == "device_offline"
        states["online"] = True
        online = _receive_event(websocket, "device_online")
        assert online["event"] == "device_online"
        # Drain a few snapshots; firmware_update must not appear for same rev.
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            msg = websocket.receive_json()
            assert msg.get("event") != "firmware_update", msg


def test_resolve_task_terminal_event_unknown_returns_none(monkeypatch, caplog):
    from routes.device_app_status_ws import _resolve_task_terminal_event

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr("routes.device_app_status_ws.task_snapshot", lambda _tid: None)

    class _Conn:
        def execute(self, *_a, **_k):
            return self

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr("routes.device_app_status_ws.connect", lambda: _Conn())
    assert _resolve_task_terminal_event("missing-task") is None
    assert any("unknown task terminal" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_send_task_transition_skips_unknown_terminal(monkeypatch):
    from routes.device_app_status_ws import _send_task_transition

    sent: list[dict] = []

    class _Ws:
        async def send_json(self, payload):
            sent.append(payload)

    monkeypatch.setattr(
        "routes.device_app_status_ws._resolve_task_terminal_event",
        lambda _tid: None,
    )
    await _send_task_transition(
        _Ws(),
        "dev-1",
        {"activeTaskId": "task-x"},
        {"activeTaskId": None},
    )
    assert sent == []
