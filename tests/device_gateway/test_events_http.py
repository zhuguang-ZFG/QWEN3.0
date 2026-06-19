from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.tasks import task_snapshot
from routes.device_gateway import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_events_endpoint_records_motion_event_with_private_auth():
    response = _client().post(
        "/device/v1/events",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": "task-http-1",
            "phase": "progress",
            "progress": {"percent": 50},
            "request_id": "req-events",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "motion_event_ack"
    assert data["task_id"] == "task-http-1"
    assert data["phase"] == "progress"
    assert data["request_id"] == "req-events"


def test_events_endpoint_preserves_firmware_failure_error():
    client = _client()
    response = client.post(
        "/device/v1/events",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": "task-fw-fail",
            "phase": "failed",
            "error_code": "E_UNSUPPORTED_BOARD",
            "error_message": "board does not support motion tasks",
        },
    )

    assert response.status_code == 200
    snapshot = task_snapshot("task-fw-fail")
    assert snapshot["status"] == "failed"
    assert snapshot["events"][0]["error"] == {
        "code": "E_UNSUPPORTED_BOARD",
        "reason": "board does not support motion tasks",
    }


def test_events_endpoint_requires_private_auth():
    response = _client().post(
        "/device/v1/events",
        headers={"Authorization": "Bearer wrong"},
        json={"type": "motion_event", "device_id": "dev-1", "task_id": "task-1", "phase": "done"},
    )

    assert response.status_code == 401


def test_events_endpoint_acks_processing_task_after_motion_event(monkeypatch):
    acked = []

    def fake_ack_processing(device_id: str, task_id: str) -> bool:
        acked.append((device_id, task_id))
        return True

    monkeypatch.setattr("routes.device_gateway.ack_processing_task", fake_ack_processing)

    response = _client().post(
        "/device/v1/events",
        headers={"Authorization": "Bearer test-private-token"},
        json={"type": "motion_event", "device_id": "dev-1", "task_id": "task-http-1", "phase": "done"},
    )

    assert response.status_code == 200
    assert acked == [("dev-1", "task-http-1")]
