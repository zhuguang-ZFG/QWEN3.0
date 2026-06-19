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


def test_cloud_to_fake_u1_rejects_unknown_route_policy(
    lima_client: TestClient, fake_device_server: dict[str, Any], fake_u1: dict[str, Any]
) -> None:
    """A motion_task with an unknown route_role is rejected by fake U1 before execution."""
    device_id = "fake-u1-device"

    home_response = _post_to_fake_device_server(
        fake_device_server,
        "/internal/v1/motion_task",
        {"device_id": device_id, "task_id": "pre-home", "capability": "home", "params": {}},
    )
    assert home_response["code"] == 0
    assert fake_u1["simulator"].state.homed is True

    with lima_client.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
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

        response = lima_client.post(
            "/device/v1/tasks",
            headers={"Authorization": "Bearer test-private-token"},
            json={"device_id": device_id, "text": "write hi", "request_id": "req-reject"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        task_id = data["task"]["task_id"]

        task_msg = ws.receive_json()
        assert task_msg["type"] == "motion_task"

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
        assert fds_response["code"] == 0
        assert fds_response["data"]["status"] == "ERROR"
        assert fds_response["data"]["error_code"] == "E009"
        assert fds_response["data"]["route_policy_rejected"] is True

        # Simulate the device reporting the failure back to the cloud.
        assert _send_motion_event(ws, device_id, task_id, "failed")["type"] == "motion_event_ack"

    status_response = lima_client.get(
        f"/device/v1/tasks/{task_id}",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] in {"failed", "done"}
