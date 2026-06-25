from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import task_snapshot
from routes.device_gateway import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class _FailingWebSocket:
    async def send_json(self, payload):
        raise RuntimeError("send failed")


def test_tasks_endpoint_creates_queued_motion_task_without_active_session(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_OUTCOME_DB", str(tmp_path / "outcome_ledger.db"))
    response = _client().post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "text": "画一个星星", "request_id": "req-task"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["sent"] is False
    assert data["queue_depth"] == 1
    assert data["task"]["type"] == "motion_task"
    assert data["task"]["capability"] == "run_path"
    assert data["task"]["request_id"] == "req-task"

    from observability.capability_evidence import recent_evidence

    rows = [r for r in recent_evidence(limit=5) if r.get("loop") == "device_gateway"]
    assert rows and rows[-1]["status"] == "queued"
    assert rows[-1]["device_id"] == "dev-1"


def test_tasks_endpoint_does_not_queue_validation_failed_task(monkeypatch):
    async def fake_create_task_from_transcript(
        device_id: str, text: str, request_id: str | None = None, **kwargs: Any
    ) -> dict:
        return {
            "type": "motion_task",
            "task_id": "task-invalid",
            "device_id": device_id,
            "capability": "run_path",
            "params": {},
            "error": {"code": "E_UNSUPPORTED_CAPABILITY", "reason": "unsupported"},
        }

    monkeypatch.setattr(
        "device_gateway.tasks.create_task_from_transcript_async",
        fake_create_task_from_transcript,
    )

    response = _client().post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "text": "invalid", "request_id": "req-invalid"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["sent"] is False
    assert data["queue_depth"] == 0
    assert data["task"]["error"]["code"] == "E_UNSUPPORTED_CAPABILITY"


def test_tasks_endpoint_publishes_task_available_when_session_is_not_local(monkeypatch):
    published = []

    async def fake_publish(device_id: str) -> None:
        published.append(device_id)

    monkeypatch.setattr("routes.device_gateway_dispatch.publish_task_available", fake_publish)

    response = _client().post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "text": "notify remote owner", "request_id": "req-notify"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert published == ["dev-1"]


def test_tasks_endpoint_flushes_queued_task_when_device_connects():
    client = _client()
    queued = client.post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "text": "写你好", "request_id": "req-queued"},
    ).json()
    assert queued["status"] == "queued"

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
        flushed_task = ws.receive_json()

    assert flushed_task["type"] == "motion_task"
    assert flushed_task["task_id"] == queued["task"]["task_id"]
    assert flushed_task["request_id"] == "req-queued"


def test_device_hello_drains_more_than_one_pending_batch():
    client = _client()
    queued_task_ids = []
    for index in range(18):
        queued = client.post(
            "/device/v1/tasks",
            headers={"Authorization": "Bearer test-private-token"},
            json={"device_id": "dev-1", "text": f"write {index}", "request_id": f"req-{index}"},
        ).json()
        queued_task_ids.append(queued["task"]["task_id"])

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
        flushed_task_ids = [ws.receive_json()["task_id"] for _ in range(18)]
        for task_id in flushed_task_ids:
            ws.send_json({"type": "motion_event", "device_id": "dev-1", "task_id": task_id, "phase": "accepted"})
            assert ws.receive_json()["type"] == "motion_event_ack"

    assert flushed_task_ids == queued_task_ids
    assert client.get("/device/v1/health").json()["pending_tasks"] == 0


def test_tasks_endpoint_requeues_when_active_session_send_fails():
    client = _client()
    failing_socket = _FailingWebSocket()
    registry.register(DeviceSession(device_id="dev-1", websocket=failing_socket))

    response = client.post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "text": "write after failure", "request_id": "req-fail"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["sent"] is False
    assert data["queue_depth"] == 1
    assert registry.get("dev-1") is None
    assert task_snapshot(data["task"]["task_id"])["status"] == "queued"


def test_tasks_endpoint_keeps_device_queues_independent():
    client = _client()
    for device_id in ("dev-1", "dev-2", "dev-1"):
        response = client.post(
            "/device/v1/tasks",
            headers={"Authorization": "Bearer test-private-token"},
            json={"device_id": device_id, "text": "写你好"},
        )
        assert response.status_code == 200

    health = client.get("/device/v1/health").json()
    assert health["pending_tasks"] == 3
