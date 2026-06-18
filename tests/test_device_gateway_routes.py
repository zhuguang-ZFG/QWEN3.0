from fastapi import FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient
import pytest
from unittest.mock import AsyncMock

import server
from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import (
    create_task_from_transcript,
    enqueue_pending_task,
    pending_count,
    pop_pending_tasks,
    task_snapshot,
)
from routes.device_gateway import (
    _dispatch_task_to_session,
    _drain_pending_tasks,
    _notify_local_session_task_available,
    _reset_for_tests,
    router,
)


@pytest.fixture(autouse=True)
def _device_gateway_test_env(monkeypatch):
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=test-device-token")
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setattr(
        "device_gateway.task_draw_params.handle_device_draw",
        AsyncMock(
            return_value={
                "status": "success",
                "image_url": "",
                "svg_path": "M 10 10 L 50 50 L 90 10 Z",
                "width": 180,
                "height": 180,
                "model": "test-draw",
                "error": None,
            }
        ),
    )
    _reset_for_tests()
    yield
    _reset_for_tests()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_server_registers_device_gateway_routes():
    http_paths = {route.path for route in server.app.routes if isinstance(route, APIRoute)}
    ws_paths = {route.path for route in server.app.routes if isinstance(route, APIWebSocketRoute)}

    assert "/device/v1/health" in http_paths
    assert "/device/v1/events" in http_paths
    assert "/device/v1/tasks" in http_paths
    assert "/device/v1/ws" in ws_paths


def test_device_gateway_health_reports_protocol_and_auth_state():
    response = _client().get("/device/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["protocol"] == "lima-device-v1"
    assert data["auth_configured"] is True
    assert data["task_store"] == {"backend": "memory", "shared_across_processes": False}


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
    async def fake_create_task_from_transcript(device_id: str, text: str, request_id: str | None = None) -> dict:
        return {
            "type": "motion_task",
            "task_id": "task-invalid",
            "device_id": device_id,
            "capability": "run_path",
            "params": {},
            "error": {"code": "E_UNSUPPORTED_CAPABILITY", "reason": "unsupported"},
        }

    monkeypatch.setattr(
        "device_gateway.task_service.create_task_from_transcript_async",
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


class _FailingWebSocket:
    async def send_json(self, payload):
        raise RuntimeError("send failed")


class _FailAfterWebSocket:
    def __init__(self, fail_after: int):
        self.fail_after = fail_after
        self.sent = []

    async def send_json(self, payload):
        if len(self.sent) >= self.fail_after:
            raise RuntimeError("send failed")
        self.sent.append(payload)


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


async def test_dispatch_task_requeues_existing_inflight_and_current_task_on_send_failure():
    websocket = _FailAfterWebSocket(fail_after=0)
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    previous = create_task_from_transcript("dev-1", "previous")
    current = create_task_from_transcript("dev-1", "current")
    session.mark_task_dispatched(previous)
    registry.register(session)

    assert await _dispatch_task_to_session(session, current) is False

    redelivered = pop_pending_tasks("dev-1", limit=10)
    assert [task["task_id"] for task in redelivered] == [previous["task_id"], current["task_id"]]
    assert registry.get("dev-1") is None


async def test_hello_pending_drain_failure_requeues_inflight_prefix_and_unsent_suffix():
    tasks = [create_task_from_transcript("dev-1", f"write {index}") for index in range(3)]
    for task in tasks:
        enqueue_pending_task("dev-1", task)
    websocket = _FailAfterWebSocket(fail_after=1)
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    registry.register(session)

    assert await _drain_pending_tasks(session) is False

    redelivered = pop_pending_tasks("dev-1", limit=10)
    assert [task["task_id"] for task in redelivered] == [task["task_id"] for task in tasks]
    assert registry.get("dev-1") is None


async def test_task_available_notification_drains_shared_queue_to_local_session():
    task = create_task_from_transcript("dev-1", "remote queued task")
    enqueue_pending_task("dev-1", task)
    websocket = _FailAfterWebSocket(fail_after=99)
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    registry.register(session)

    await _notify_local_session_task_available("dev-1")

    assert [payload["task_id"] for payload in websocket.sent] == [task["task_id"]]
    assert task_snapshot(task["task_id"])["status"] == "dispatched"


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


def test_websocket_motion_event_acks_processing_task(monkeypatch):
    acked = []

    def fake_ack_processing(device_id: str, task_id: str) -> bool:
        acked.append((device_id, task_id))
        return True

    monkeypatch.setattr("routes.device_gateway_ws_handlers.ack_processing_task", fake_ack_processing)

    client = _client()
    with client.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
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


def test_websocket_transcript_failed_task_is_not_dispatched(monkeypatch):
    async def fake_create_task_from_transcript(device_id: str, text: str, request_id: str | None = None) -> dict:
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
    with client.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
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


# ── Task status query tests ──────────────────────────────────────────────────


def test_task_status_returns_404_for_nonexistent():
    """查询不存在的任务返回 404"""
    response = _client().get(
        "/device/v1/tasks/nonexistent-task-id",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 404


def test_task_status_returns_task_info():
    """查询存在的任务返回任务信息"""
    # 先创建一个任务
    task = create_task_from_transcript("dev-1", "home")

    response = _client().get(
        f"/device/v1/tasks/{task['task_id']}",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task["task_id"]
    assert "status" in data
    assert "task" in data


def test_task_list_returns_tasks():
    """查询任务列表返回任务"""
    # 创建一些任务
    create_task_from_transcript("dev-1", "home")
    create_task_from_transcript("dev-1", "write Hello")

    response = _client().get(
        "/device/v1/tasks?device_id=dev-1",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert "count" in data
    assert data["count"] >= 2


def test_task_list_filter_by_status():
    """按状态过滤任务列表"""
    # 创建任务
    create_task_from_transcript("dev-1", "home")

    response = _client().get(
        "/device/v1/tasks?device_id=dev-1&status=created",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    # 所有返回的任务都应该是 created 状态
    for task in data["tasks"]:
        assert task.get("status") == "created"


def test_task_list_requires_auth():
    """查询任务列表需要认证"""
    response = _client().get("/device/v1/tasks")
    assert response.status_code == 401 or response.status_code == 403


def test_task_status_requires_auth():
    """查询任务状态需要认证"""
    response = _client().get("/device/v1/tasks/test-task-id")
    assert response.status_code == 401 or response.status_code == 403


# ── Drawing history tests ────────────────────────────────────────────────────


def test_drawing_history_returns_empty_for_new_device():
    """新设备的绘图历史为空"""
    response = _client().get(
        "/device/v1/devices/dev-new/history",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "dev-new"
    assert data["history"] == []
    assert data["count"] == 0


def test_drawing_history_returns_artifacts():
    """绘图历史返回制品"""
    from device_artifacts.store import artifact_store

    # 创建一个任务并记录制品
    task = create_task_from_transcript("dev-1", "draw cat")
    artifact_store.put_artifact(
        task_id=task["task_id"],
        artifact_type="route_evidence",
        content={"device_id": "dev-1", "route_role": "device_draw"},
        retention_days=30,
    )

    response = _client().get(
        "/device/v1/devices/dev-1/history",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "dev-1"
    assert len(data["history"]) >= 1
    assert data["history"][0]["artifact_type"] == "route_evidence"


def test_drawing_history_filter_by_type():
    """按类型过滤绘图历史"""
    from device_artifacts.store import artifact_store

    # 创建不同类型的制品
    task = create_task_from_transcript("dev-1", "draw star")
    artifact_store.put_artifact(
        task_id=task["task_id"],
        artifact_type="route_evidence",
        content={"device_id": "dev-1"},
        retention_days=30,
    )
    artifact_store.put_artifact(
        task_id=task["task_id"],
        artifact_type="preview_svg",
        content={"device_id": "dev-1", "svg": "<svg>...</svg>"},
        retention_days=30,
    )

    # 过滤 route_evidence
    response = _client().get(
        "/device/v1/devices/dev-1/history?artifact_type=route_evidence",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(h["artifact_type"] == "route_evidence" for h in data["history"])


def test_drawing_history_pagination():
    """绘图历史分页"""
    from device_artifacts.store import artifact_store

    # 创建多个制品
    for i in range(5):
        task = create_task_from_transcript("dev-1", f"draw shape {i}")
        artifact_store.put_artifact(
            task_id=task["task_id"],
            artifact_type="route_evidence",
            content={"device_id": "dev-1", "index": i},
            retention_days=30,
        )

    # 测试分页
    response = _client().get(
        "/device/v1/devices/dev-1/history?limit=2&offset=0",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["history"]) == 2
    assert data["count"] == 2
    assert data["offset"] == 0
    assert data["limit"] == 2


def test_drawing_history_requires_auth():
    """查询绘图历史需要认证"""
    response = _client().get("/device/v1/devices/dev-1/history")
    assert response.status_code == 401 or response.status_code == 403
