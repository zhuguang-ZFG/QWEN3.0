"""Cloud 'home' command closed-loop test."""

from __future__ import annotations

from fastapi.testclient import TestClient

from typing import Any

from fake_u1_helpers import (
    fake_device_server,
    fake_u1,
    lima_client,
    _post_to_fake_device_server,
    _send_motion_event,
)


def test_cloud_to_fake_u1_home_loop(lima_client: TestClient, fake_device_server: dict[str, Any]) -> None:
    """Cloud 'home' command executes on fake U1 and reaches terminal 'done' state."""
    device_id = "fake-u1-device"

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
            json={"device_id": device_id, "text": "home", "request_id": "req-home"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        task_id = data["task"]["task_id"]

        task_msg = ws.receive_json()
        assert task_msg["type"] == "motion_task"
        assert task_msg["task_id"] == task_id
        assert task_msg["capability"] == "home"

        assert _send_motion_event(ws, device_id, task_id, "accepted")["type"] == "motion_event_ack"

        # Bridge the LiMa motion_task into the fake U1 private protocol.
        fds_response = _post_to_fake_device_server(
            fake_device_server,
            "/internal/v1/motion_task",
            {
                "device_id": device_id,
                "task_id": task_id,
                "capability": task_msg["capability"],
                "route_policy": task_msg.get("route_policy", {}),
                "params": task_msg.get("params", {}),
            },
        )
        assert fds_response["code"] == 0
        assert fds_response["data"]["status"] == "IDLE"

        assert _send_motion_event(ws, device_id, task_id, "running")["type"] == "motion_event_ack"
        assert _send_motion_event(ws, device_id, task_id, "done")["type"] == "motion_event_ack"

    status_response = lima_client.get(
        f"/device/v1/tasks/{task_id}",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "done"

    from observability.capability_evidence import recent_evidence

    evidence = [r for r in recent_evidence(limit=20) if r.get("task_id") == task_id]
    assert any(r.get("status") == "sent" and r.get("entrypoint") == "/device/v1/tasks" for r in evidence)
