from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.tasks import pending_count
from routes.device_gateway import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_fake_u8_hello_heartbeat_transcript_motion_event_loop():
    client = _client()
    with client.websocket_connect("/device/v1/ws", headers={"Authorization": "Bearer test-device-token"}) as ws:
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


def test_websocket_transcript_failed_task_is_not_dispatched(monkeypatch):
    async def fake_create_task_from_transcript(device_id: str, text: str, request_id: str | None = None, **kwargs: Any) -> dict:
        return {
            "type": "motion_task",
            "task_id": "task-ws-invalid",
            "device_id": device_id,
            "capability": "run_path",
            "params": {},
            "error": {"code": "E_BAD_PARAMS", "reason": "bad params"},
        }

    monkeypatch.setattr(
        "routes.device_gateway_ws_handlers.create_task_from_transcript_async",
        fake_create_task_from_transcript,
    )

    client = _client()
    with client.websocket_connect("/device/v1/ws", headers={"Authorization": "Bearer test-device-token"}) as ws:
        ws.send_json(
            {
                "type": "hello",
                "protocol": "lima-device-v1",
                "device_id": "dev-1",
                "capabilities": ["run_path"],
            }
        )
        assert ws.receive_json()["type"] == "hello_ack"
        ws.send_json({"type": "transcript", "device_id": "dev-1", "text": "bad", "request_id": "req-bad"})
        failed = ws.receive_json()

    assert failed["type"] == "motion_task_failed"
    assert failed["task_id"] == "task-ws-invalid"
    assert failed["error"]["code"] == "E_BAD_PARAMS"
    assert pending_count("dev-1") == 0


def test_websocket_returns_stable_error_before_hello():
    client = _client()
    with client.websocket_connect("/device/v1/ws", headers={"Authorization": "Bearer test-device-token"}) as ws:
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
    with client.websocket_connect("/device/v1/ws", headers={"Authorization": "Bearer wrong"}) as ws:
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


def test_websocket_motion_event_acks_processing_task(monkeypatch):
    acked = []

    def fake_ack_processing(device_id: str, task_id: str) -> bool:
        acked.append((device_id, task_id))
        return True

    monkeypatch.setattr("device_gateway.task_lifecycle.ack_processing_task", fake_ack_processing)

    client = _client()
    with client.websocket_connect("/device/v1/ws", headers={"Authorization": "Bearer test-device-token"}) as ws:
        ws.send_json(
            {
                "type": "hello",
                "protocol": "lima-device-v1",
                "device_id": "dev-1",
                "capabilities": [],
            }
        )
        assert ws.receive_json()["type"] == "hello_ack"
        ws.send_json({"type": "motion_event", "device_id": "dev-1", "task_id": "task-ws-1", "phase": "done"})
        assert ws.receive_json()["type"] == "motion_event_ack"

    assert acked == [("dev-1", "task-ws-1")]
