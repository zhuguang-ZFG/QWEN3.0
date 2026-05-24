import os

from fastapi import FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient

import server
from routes.device_gateway import _reset_for_tests, router


def setup_function():
    os.environ["LIMA_DEVICE_TOKENS"] = "dev-1=test-device-token"
    _reset_for_tests()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_server_registers_device_gateway_routes():
    http_paths = {route.path for route in server.app.routes if isinstance(route, APIRoute)}
    ws_paths = {route.path for route in server.app.routes if isinstance(route, APIWebSocketRoute)}

    assert "/device/v1/health" in http_paths
    assert "/device/v1/ws" in ws_paths


def test_device_gateway_health_reports_protocol_and_auth_state():
    response = _client().get("/device/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["protocol"] == "lima-device-v1"
    assert data["auth_configured"] is True


def test_fake_u8_hello_heartbeat_transcript_motion_event_loop():
    client = _client()
    with client.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
        ws.send_json(
            {
                "type": "hello",
                "protocol": "lima-device-v1",
                "device_id": "dev-1",
                "fw_rev": "u8-test",
                "capabilities": ["run_path"],
            }
        )
        assert ws.receive_json()["type"] == "hello_ack"

        ws.send_json({"type": "heartbeat", "device_id": "dev-1", "uptime_ms": 123})
        heartbeat_ack = ws.receive_json()
        assert heartbeat_ack["type"] == "heartbeat_ack"
        assert heartbeat_ack["uptime_ms"] == 123

        ws.send_json({"type": "transcript", "device_id": "dev-1", "text": "写你好", "request_id": "req-1"})
        motion_task = ws.receive_json()
        assert motion_task["type"] == "motion_task"
        assert motion_task["capability"] == "run_path"
        assert motion_task["request_id"] == "req-1"
        assert motion_task["params"]["source_capability"] == "write_text"

        ws.send_json(
            {
                "type": "motion_event",
                "device_id": "dev-1",
                "task_id": motion_task["task_id"],
                "phase": "progress",
                "progress": {"done_segments": 1, "total_segments": 4, "percent": 25},
            }
        )
        event_ack = ws.receive_json()
        assert event_ack["type"] == "motion_event_ack"
        assert event_ack["task_id"] == motion_task["task_id"]
        assert event_ack["phase"] == "progress"


def test_websocket_returns_stable_error_before_hello():
    client = _client()
    with client.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
        ws.send_json({"type": "heartbeat", "device_id": "dev-1", "uptime_ms": 1, "request_id": "req-before-hello"})
        error = ws.receive_json()

    assert error == {
        "type": "error",
        "code": "E_HELLO_REQUIRED",
        "message": "hello must be sent before other messages",
        "request_id": "req-before-hello",
    }


def test_websocket_rejects_invalid_device_token():
    client = _client()
    with client.websocket_connect("/device/v1/ws?token=wrong") as ws:
        ws.send_json(
            {
                "type": "hello",
                "protocol": "lima-device-v1",
                "device_id": "dev-1",
                "capabilities": [],
                "request_id": "req-auth",
            }
        )
        error = ws.receive_json()

    assert error == {
        "type": "error",
        "code": "E_UNAUTHORIZED_DEVICE",
        "message": "device token is invalid",
        "request_id": "req-auth",
    }

