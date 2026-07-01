"""Unknown route policy rejection closed-loop test."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from fake_u1_helpers import (
    fake_device_server,
    fake_u1,
    lima_client,
    _post_to_fake_device_server,
    _send_motion_event,
)


def _home_device(fake_device_server: dict[str, Any], fake_u1: dict[str, Any], device_id: str) -> None:
    """Home the device via the fake-device-server internal endpoint."""
    home_response = _post_to_fake_device_server(
        fake_device_server,
        "/internal/v1/motion_task",
        {"device_id": device_id, "task_id": "pre-home", "capability": "home", "params": {}},
    )
    assert home_response["code"] == 0
    assert fake_u1["simulator"].state.homed is True


def _ws_send_hello(ws, device_id: str) -> None:
    """Send a hello handshake and assert hello_ack."""
    ws.send_json(
        {
            "type": "hello",
            "protocol": "lima-device-v1",
            "device_id": device_id,
            "fw_rev": "u1-test",
            "capabilities": ["run_path"],
        }
    )
    assert ws.receive_json()["type"] == "hello_ack"


def _send_task_and_receive(lima_client: TestClient, ws, device_id: str, text: str, request_id: str):
    """POST a task, assert sent, and receive the motion_task from WS."""
    response = lima_client.post(
        "/device/v1/tasks",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": device_id, "text": text, "request_id": request_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    task_id = data["task"]["task_id"]
    task_msg = ws.receive_json()
    assert task_msg["type"] == "motion_task"
    return task_id, task_msg


def _assert_rejection(fds_response: dict[str, Any]) -> None:
    """Assert the fake U1 rejected the task with E009."""
    assert fds_response["code"] == 0
    assert fds_response["data"]["status"] == "ERROR"
    assert fds_response["data"]["error_code"] == "E009"
    assert fds_response["data"]["route_policy_rejected"] is True


def _assert_task_failed_or_done(lima_client: TestClient, task_id: str) -> None:
    """Assert the task has reached 'failed' or 'done' status."""
    status_response = lima_client.get(
        f"/device/v1/tasks/{task_id}",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] in {"failed", "done"}


def test_cloud_to_fake_u1_rejects_unknown_route_policy(
    lima_client: TestClient, fake_device_server: dict[str, Any], fake_u1: dict[str, Any]
) -> None:
    """A motion_task with an unknown route_role is rejected by fake U1 before execution."""
    device_id = "fake-u1-device"
    _home_device(fake_device_server, fake_u1, device_id)

    with lima_client.websocket_connect("/device/v1/ws", headers={"Authorization": "Bearer test-device-token"}) as ws:
        _ws_send_hello(ws, device_id)
        task_id, task_msg = _send_task_and_receive(lima_client, ws, device_id, "write hi", "req-reject")

        assert _send_motion_event(ws, device_id, task_id, "accepted")["type"] == "motion_event_ack"

        # Poison the route_policy with an unknown role before forwarding to fake U1.
        bad_policy = dict(task_msg.get("route_policy", {}))
        bad_policy["route_role"] = "invalid_role"
        fds_response = _post_to_fake_device_server(
            fake_device_server,
            "/internal/v1/motion_task",
            {
                "device_id": device_id,
                "task_id": task_id,
                "capability": task_msg["capability"],
                "route_policy": bad_policy,
                "params": task_msg.get("params", {}),
            },
        )
        _assert_rejection(fds_response)

        # Simulate the device reporting the failure back to the cloud.
        assert _send_motion_event(ws, device_id, task_id, "failed")["type"] == "motion_event_ack"

    _assert_task_failed_or_done(lima_client, task_id)
