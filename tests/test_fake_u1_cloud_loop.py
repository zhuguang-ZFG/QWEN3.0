"""LiMa cloud → fake U1 motion execution closed-loop evidence (G1 follow-up).

This test wires LiMa's `/device/v1/tasks` and `/device/v1/events` endpoints to
`esp32S_XYZ/tools/fake_device_server` and `esp32S_XYZ/tools/fake_u1`, proving that
a cloud-issued device command can be dispatched over WebSocket, translated to
the Edge-D private protocol, executed by the fake U1 simulator, and reported
back to the cloud as a terminal `motion_event`.
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Allow importing the ESP32 fake tooling from the sibling reference repo.
_ESP32_TOOLS = Path(__file__).resolve().parent.parent / "esp32S_XYZ" / "tools"
sys.path.insert(0, str(_ESP32_TOOLS))

from fake_device_server.app import FakeDeviceServerHandler  # noqa: E402
from fake_device_server.app import motion_task_to_u1_commands  # noqa: E402
from fake_u1.app import FakeU1Simulator, FakeU1TCPServer  # noqa: E402


@pytest.fixture
def fake_u1() -> Any:
    """Threaded fake U1 TCP server with a fresh simulator."""
    simulator = FakeU1Simulator()
    server = FakeU1TCPServer(("127.0.0.1", 0), simulator)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"host": host, "port": port, "simulator": simulator, "server": server}
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def fake_device_server(fake_u1: dict[str, Any]) -> dict[str, Any]:
    """Threaded fake device server bridged to the running fake U1."""
    import fake_device_server.app as fds_app

    fds_app.FAKE_U1_HOST = fake_u1["host"]
    fds_app.FAKE_U1_PORT = fake_u1["port"]
    FakeDeviceServerHandler.business_base_url = ""
    FakeDeviceServerHandler.internal_token = ""

    server = HTTPServer(("127.0.0.1", 0), FakeDeviceServerHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"host": host, "port": port, "server": server}
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def lima_client(monkeypatch: Any, tmp_path: Path) -> TestClient:
    """LiMa device gateway routes with in-memory stores and deterministic auth."""
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "fake-u1-device=test-device-token")
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setenv("LIMA_OUTCOME_DB", str(tmp_path / "outcome.db"))

    from routes.device_gateway import router, _reset_for_tests

    _reset_for_tests()
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    yield client
    _reset_for_tests()


def _post_to_fake_device_server(fds: dict[str, Any], path: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        f"http://{fds['host']}:{fds['port']}{path}",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _send_motion_event(ws: Any, device_id: str, task_id: str, phase: str) -> dict[str, Any]:
    ws.send_json({
        "type": "motion_event",
        "device_id": device_id,
        "task_id": task_id,
        "phase": phase,
    })
    return ws.receive_json()


def test_cloud_to_fake_u1_home_loop(lima_client: TestClient, fake_device_server: dict[str, Any]) -> None:
    """Cloud 'home' command executes on fake U1 and reaches terminal 'done' state."""
    device_id = "fake-u1-device"

    with lima_client.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
        ws.send_json({
            "type": "hello",
            "protocol": "lima-device-v1",
            "device_id": device_id,
            "fw_rev": "u1-test",
            "capabilities": ["run_path"],
        })
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


def test_cloud_to_fake_u1_write_text_loop(
    lima_client: TestClient, fake_device_server: dict[str, Any], fake_u1: dict[str, Any]
) -> None:
    """Cloud 'write hi' command renders to a path, executes on fake U1, and reaches 'done'."""
    device_id = "fake-u1-device"

    # Ensure the fake U1 is homed before executing a run_path task.
    home_response = _post_to_fake_device_server(
        fake_device_server,
        "/internal/v1/motion_task",
        {"device_id": device_id, "task_id": "pre-home", "capability": "home", "params": {}},
    )
    assert home_response["code"] == 0
    assert fake_u1["simulator"].state.homed is True

    with lima_client.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
        ws.send_json({
            "type": "hello",
            "protocol": "lima-device-v1",
            "device_id": device_id,
            "fw_rev": "u1-test",
            "capabilities": ["run_path"],
        })
        assert ws.receive_json()["type"] == "hello_ack"

        response = lima_client.post(
            "/device/v1/tasks",
            headers={"Authorization": "Bearer test-private-token"},
            json={"device_id": device_id, "text": "write hi", "request_id": "req-write"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        task_id = data["task"]["task_id"]

        task_msg = ws.receive_json()
        assert task_msg["type"] == "motion_task"
        assert task_msg["task_id"] == task_id
        assert task_msg["capability"] == "run_path"
        assert "path" in task_msg.get("params", {})

        assert _send_motion_event(ws, device_id, task_id, "accepted")["type"] == "motion_event_ack"

        fds_response = _post_to_fake_device_server(
            fake_device_server,
            "/internal/v1/motion_task",
            {
                "device_id": device_id,
                "task_id": task_id,
                "capability": task_msg["capability"],
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


def test_cloud_to_fake_u1_draw_generated_svg_loop(
    lima_client: TestClient, fake_device_server: dict[str, Any], fake_u1: dict[str, Any]
) -> None:
    """Cloud 'svg <path>' drawing command renders to a path, executes on fake U1, and reaches 'done'.

    This covers the ``draw_generated`` capability for vector-like prompts that are already
    SVG path data.  The cloud renders them locally, dispatches a ``run_path`` motion_task,
    and the fake U1 bridge translates it into Edge-D PATH_BEGIN/PATH_SEG/PATH_END commands.
    """
    device_id = "fake-u1-device"

    # Ensure the fake U1 is homed before executing a run_path task.
    home_response = _post_to_fake_device_server(
        fake_device_server,
        "/internal/v1/motion_task",
        {"device_id": device_id, "task_id": "pre-home", "capability": "home", "params": {}},
    )
    assert home_response["code"] == 0
    assert fake_u1["simulator"].state.homed is True

    with lima_client.websocket_connect("/device/v1/ws?token=test-device-token") as ws:
        ws.send_json({
            "type": "hello",
            "protocol": "lima-device-v1",
            "device_id": device_id,
            "fw_rev": "u1-test",
            "capabilities": ["run_path"],
        })
        assert ws.receive_json()["type"] == "hello_ack"

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
        assert task_msg["type"] == "motion_task"
        assert task_msg["task_id"] == task_id
        assert task_msg["capability"] == "run_path"

        params = task_msg.get("params", {})
        assert "path" in params
        assert params.get("source_capability") == "draw_generated"
        assert params.get("prompt") == svg_d
        assert len(params["path"]) >= 3

        assert _send_motion_event(ws, device_id, task_id, "accepted")["type"] == "motion_event_ack"

        fds_response = _post_to_fake_device_server(
            fake_device_server,
            "/internal/v1/motion_task",
            {
                "device_id": device_id,
                "task_id": task_id,
                "capability": task_msg["capability"],
                "params": params,
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


def test_cloud_task_command_translation_matches_u1_protocol() -> None:
    """The bridge converts LiMa motion_task payloads into valid Edge-D command sequences."""
    commands = motion_task_to_u1_commands({
        "device_id": "dev-1",
        "task_id": "task-path",
        "capability": "run_path",
        "params": {
            "feed": 900,
            "path": [
                {"cmd": "M", "x": 0, "y": 0, "z": 0},
                {"cmd": "L", "x": 10, "y": 0, "z": 0},
            ],
        },
    })
    assert [cmd["cmd"] for cmd in commands] == ["PATH_BEGIN", "PATH_SEG", "PATH_SEG", "PATH_END"]
    assert commands[0]["total_segments"] == 2
