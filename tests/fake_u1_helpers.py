"""Shared fixtures and helpers for fake U1 closed-loop tests."""

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

    from routes.device_gateway import router
    from routes.device_gateway_helpers import _reset_for_tests

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
    ws.send_json(
        {
            "type": "motion_event",
            "device_id": device_id,
            "task_id": task_id,
            "phase": phase,
        }
    )
    return ws.receive_json()
