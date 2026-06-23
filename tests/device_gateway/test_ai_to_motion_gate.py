"""M15 AI→Motion release gate: end-to-end traceability tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_artifacts.store import artifact_store
from device_gateway.sessions import DeviceSession, registry
from device_gateway.task_events import process_motion_event_core
from device_gateway.tasks import (
    DeviceTaskRequest,
    create_and_route_task,
    reset_tasks_for_tests,
    task_snapshot,
)
from device_ledger.store import ledger_store
from routes.device_gateway import router


@pytest.fixture(autouse=True)
def _reset_state():
    registry.clear()
    reset_tasks_for_tests()
    yield
    registry.clear()
    reset_tasks_for_tests()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _route_evidence_for_task(task_id: str):
    records = artifact_store.artifacts_for_task(task_id, "route_evidence")
    return [r.content for r in records]


@pytest.mark.asyncio
async def test_create_and_route_task_records_request_id_and_entrypoint() -> None:
    result = await create_and_route_task(
        DeviceTaskRequest(
            device_id="dev-1",
            text="home",
            request_id="req-http-1",
            source="http",
            entrypoint="http_device_tasks",
        )
    )

    task = result.task
    assert task["request_id"] == "req-http-1"
    assert task["entrypoint"] == "http_device_tasks"

    evidence = _route_evidence_for_task(task["task_id"])
    assert evidence
    assert evidence[0]["request_id"] == "req-http-1"
    assert evidence[0]["entrypoint"] == "http_device_tasks"
    assert evidence[0]["route_role"] == task["route_policy"]["route_role"]


def test_http_tasks_endpoint_records_entrypoint_and_request_id() -> None:
    client = _client()
    response = client.post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "text": "home", "request_id": "req-http-2"},
    )
    assert response.status_code == 200
    data = response.json()
    task = data["task"]
    assert task["entrypoint"] == "http_device_tasks"
    assert task["request_id"] == "req-http-2"

    evidence = _route_evidence_for_task(task["task_id"])
    assert evidence
    assert evidence[-1]["entrypoint"] == "http_device_tasks"
    assert evidence[-1]["request_id"] == "req-http-2"


def test_ws_hello_drain_preserves_request_id_and_entrypoint() -> None:
    client = _client()
    queued = client.post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "text": "home", "request_id": "req-ws-drain"},
    ).json()
    assert queued["status"] == "queued"
    task_id = queued["task"]["task_id"]

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
        motion_task = ws.receive_json()

    assert motion_task["type"] == "motion_task"
    assert motion_task["task_id"] == task_id
    assert motion_task["request_id"] == "req-ws-drain"

    evidence = _route_evidence_for_task(task_id)
    assert evidence
    assert evidence[-1]["request_id"] == "req-ws-drain"
    assert evidence[-1]["entrypoint"] == "http_device_tasks"


def test_ws_transcript_creates_entrypoint_evidence() -> None:
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
        ws.send_json(
            {
                "type": "transcript",
                "device_id": "dev-1",
                "text": "home",
                "request_id": "req-transcript-1",
            }
        )
        motion_task = ws.receive_json()

    assert motion_task["type"] == "motion_task"
    task_id = motion_task["task_id"]
    assert motion_task["request_id"] == "req-transcript-1"

    evidence = _route_evidence_for_task(task_id)
    assert evidence
    assert evidence[-1]["request_id"] == "req-transcript-1"
    assert evidence[-1]["entrypoint"] == "ws_transcript"


@pytest.mark.asyncio
async def test_blocking_path_records_route_evidence_with_error_code() -> None:
    from device_gateway.task_creation import project_to_motion_task_async

    task = await project_to_motion_task_async(
        "dev-1",
        {"capability": "unsupported_xyz", "params": {}, "source": "test"},
        request_id="req-block-1",
    )
    assert task.get("error")
    task_id = task["task_id"]

    evidence = _route_evidence_for_task(task_id)
    assert evidence
    assert evidence[-1]["request_id"] == "req-block-1"
    assert evidence[-1]["error_code"]


@pytest.mark.asyncio
async def test_terminal_event_creates_terminal_result_and_device_consumed_evidence() -> None:
    result = await create_and_route_task(
        DeviceTaskRequest(device_id="dev-1", text="home", request_id="req-terminal-1")
    )
    task = result.task
    task_id = task["task_id"]

    process_motion_event_core(
        "dev-1",
        {
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": task_id,
            "phase": "done",
            "route_policy_evidence": {
                "route_role": task["route_policy"]["route_role"],
                "backend": task["route_policy"].get("backend", ""),
            },
        },
    )

    snapshot = task_snapshot(task_id)
    assert snapshot is not None
    assert snapshot["status"] == "done"

    terminal_records = artifact_store.artifacts_for_task(task_id, "terminal_result")
    assert terminal_records
    assert terminal_records[0].content["phase"] == "done"
    assert terminal_records[0].content.get("device_id") == "dev-1"

    consumed = _route_evidence_for_task(task_id)
    consumed_scenarios = [c["scenario"] for c in consumed]
    assert "device_consumed" in consumed_scenarios

    terminal_events = [e for e in ledger_store.events_for_task(task_id) if e.event_type == "task_terminal"]
    assert terminal_events


def test_task_status_endpoint_returns_terminal_phase_and_result() -> None:
    client = _client()
    created = client.post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "text": "home", "request_id": "req-status-1"},
    ).json()
    task_id = created["task"]["task_id"]

    client.post(
        "/device/v1/events",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": task_id,
            "phase": "failed",
            "error": {"code": "E_MOTION_FAILED", "reason": "simulated failure"},
        },
    )

    status_response = client.get(f"/device/v1/tasks/{task_id}", headers={"Authorization": "Bearer test-private-token"})
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["terminal_phase"] == "failed"
    assert data["terminal_result"] is not None
    assert data["terminal_result"]["content"]["phase"] == "failed"


def test_disconnect_recovery_preserves_terminal_result() -> None:
    client = _client()
    created = client.post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "text": "home", "request_id": "req-recovery-1"},
    ).json()
    task_id = created["task"]["task_id"]

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
        motion_task = ws.receive_json()
        assert motion_task["task_id"] == task_id

    # Simulate reconnect and terminal event
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
        # The previously dispatched task is re-queued and drained again.
        re_dispatch = ws.receive_json()
        assert re_dispatch["type"] == "motion_task"
        assert re_dispatch["task_id"] == task_id
        # Device reports lifecycle phases leading to terminal result.
        for phase in ("accepted", "running", "done"):
            ws.send_json(
                {
                    "type": "motion_event",
                    "device_id": "dev-1",
                    "task_id": task_id,
                    "phase": phase,
                }
            )
            assert ws.receive_json()["type"] == "motion_event_ack"

    status_response = client.get(f"/device/v1/tasks/{task_id}", headers={"Authorization": "Bearer test-private-token"})
    data = status_response.json()
    assert data["terminal_phase"] == "done"
    assert data["terminal_result"] is not None
