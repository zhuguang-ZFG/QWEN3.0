"""Cloud SVG drawing command closed-loop test."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from fake_u1_helpers import (
    fake_device_server,  # noqa: F401  pytest fixture injected via parameter name (d)
    fake_u1,  # noqa: F401  pytest fixture injected via parameter name (d)
    lima_client,  # noqa: F401  pytest fixture injected via parameter name (d)
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


def _assert_svg_task_msg(task_msg: dict[str, Any], task_id: str, svg_d: str) -> None:
    """Assert SVG-specific fields in the motion_task message."""
    assert task_msg["type"] == "motion_task"
    assert task_msg["task_id"] == task_id
    assert task_msg["capability"] == "run_path"
    params = task_msg.get("params", {})
    assert "path" in params
    assert params.get("source_capability") == "draw_generated"
    assert params.get("prompt") == svg_d
    assert len(params["path"]) >= 3


def _bridge_and_run_motion(
    ws, fake_device_server: dict[str, Any], device_id: str, task_msg: dict[str, Any], task_id: str
) -> None:
    """Accept the task, bridge to fake U1, and run through running→done."""
    assert _send_motion_event(ws, device_id, task_id, "accepted")["type"] == "motion_event_ack"
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


def _assert_task_done(lima_client: TestClient, task_id: str) -> None:
    """Assert the task has reached 'done' status."""
    status_response = lima_client.get(
        f"/device/v1/tasks/{task_id}",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "done"


def test_cloud_to_fake_u1_draw_generated_svg_loop(
    lima_client: TestClient, fake_device_server: dict[str, Any], fake_u1: dict[str, Any]
) -> None:
    """Cloud 'svg <path>' drawing command renders to a path, executes on fake U1, and reaches 'done'.

    This covers the ``draw_generated`` capability for vector-like prompts that are already
    SVG path data.  The cloud renders them locally, dispatches a ``run_path`` motion_task,
    and the fake U1 bridge translates it into Edge-D PATH_BEGIN/PATH_SEG/PATH_END commands.
    """
    device_id = "fake-u1-device"
    _home_device(fake_device_server, fake_u1, device_id)

    with lima_client.websocket_connect("/device/v1/ws", headers={"Authorization": "Bearer test-device-token"}) as ws:
        _ws_send_hello(ws, device_id)

        svg_d = "M0,0 L10,0 L10,10"
        response = lima_client.post(
            "/device/v1/tasks",
            headers={"Authorization": "Bearer test-private-token"},
            json={"device_id": device_id, "text": f"svg {svg_d}", "request_id": "req-draw-svg"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        task_id = data["task"]["task_id"]

        task_msg = ws.receive_json()
        _assert_svg_task_msg(task_msg, task_id, svg_d)
        _bridge_and_run_motion(ws, fake_device_server, device_id, task_msg, task_id)

    _assert_task_done(lima_client, task_id)
