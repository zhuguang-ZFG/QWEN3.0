import time

import pytest
from starlette.websockets import WebSocketDisconnect

from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding, token
from device_gateway.sessions import DeviceSession, registry


# Polling interval used by the status WebSocket. Tests patch it to 50 ms.
_POLL_INTERVAL = 0.05


def _auth_query(account_id: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token(account_id)}"}


def test_device_status_rest_offline(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.get("/device/v1/app/devices/dev-1/status", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {
        "deviceId": "dev-1",
        "online": False,
        "connectedAt": None,
        "working": False,
        "activeTaskId": None,
        "firmwareVersion": None,
        "protocolVersion": None,
        "lastSeenAt": None,
    }


def test_device_status_rest_online(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    session = DeviceSession(
        device_id="dev-1",
        websocket=object(),
        fw_rev="2.0.0",
        protocol_version="lima-device-v2",
    )
    registry.register(session)

    response = client.get("/device/v1/app/devices/dev-1/status", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["deviceId"] == "dev-1"
    assert payload["online"] is True
    assert payload["connectedAt"] is not None
    assert payload["firmwareVersion"] == "2.0.0"
    assert payload["protocolVersion"] == "lima-device-v2"
    assert payload["lastSeenAt"] is not None
    assert payload["working"] is False
    assert payload["activeTaskId"] is None


def test_device_status_rest_active_task(tmp_path, monkeypatch):
    client, store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    session = DeviceSession(device_id="dev-1", websocket=object())
    registry.register(session)
    store.create_task_state(
        {
            "type": "motion_task",
            "task_id": "task-001",
            "device_id": "dev-1",
            "capability": "run_path",
            "source": "voice",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}]},
            "request_id": "req-001",
        },
        status="running",
    )

    response = client.get("/device/v1/app/devices/dev-1/status", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["online"] is True
    assert payload["working"] is True
    assert payload["activeTaskId"] == "task-001"


def test_device_status_rest_rejects_unbound_account(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.get("/device/v1/app/devices/dev-1/status", headers=headers("a-other"))
    assert response.status_code == 403, response.text


def test_device_status_ws_connect_and_snapshot(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr("routes.device_app_status_ws._POLL_INTERVAL", _POLL_INTERVAL)
    seed_account_and_device()
    seed_binding()

    with client.websocket_connect(
        "/device/v1/app/devices/dev-1/ws", params=_auth_query("a-owner")
    ) as websocket:
        message = websocket.receive_json()
        assert message["event"] == "status_snapshot"
        assert message["payload"]["deviceId"] == "dev-1"
        assert message["payload"]["online"] is False


def test_device_status_ws_rejects_missing_token(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/device/v1/app/devices/dev-1/ws"):
            pass


def test_device_status_ws_rejects_unbound_account(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/device/v1/app/devices/dev-1/ws", params=_auth_query("a-other")
        ):
            pass


def _receive_event(websocket, event_name: str, timeout: float = _POLL_INTERVAL * 4):
    """Read messages until the requested event arrives, skipping periodic snapshots."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        message = websocket.receive_json()
        if message["event"] == event_name:
            return message
    raise AssertionError(f"timed out waiting for event {event_name!r}")


def test_device_status_ws_online_offline_transition(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr("routes.device_app_status_ws._POLL_INTERVAL", _POLL_INTERVAL)
    seed_account_and_device()
    seed_binding()

    with client.websocket_connect(
        "/device/v1/app/devices/dev-1/ws", params=_auth_query("a-owner")
    ) as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["event"] == "status_snapshot"
        assert snapshot["payload"]["online"] is False

        session = DeviceSession(device_id="dev-1", websocket=object())
        registry.register(session)

        online_event = _receive_event(websocket, "device_online")
        assert online_event["payload"]["deviceId"] == "dev-1"

        online_snapshot = websocket.receive_json()
        assert online_snapshot["event"] == "status_snapshot"
        assert online_snapshot["payload"]["online"] is True

        registry.unregister("dev-1", session.websocket)

        offline_event = _receive_event(websocket, "device_offline")
        assert offline_event["payload"]["deviceId"] == "dev-1"

        offline_snapshot = websocket.receive_json()
        assert offline_snapshot["event"] == "status_snapshot"
        assert offline_snapshot["payload"]["online"] is False
