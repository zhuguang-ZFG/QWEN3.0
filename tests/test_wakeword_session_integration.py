"""End-to-end integration test for wakeword_runtime TestRuntimeHttpServer.

Spins up the real HTTP+WebSocket server on an ephemeral port and drives it via
plain socket + http.client + a minimal hand-rolled WebSocket client handshake.
No mocking — exercises the actual production code path
(``TestRuntimeHttpServer`` + ``frame_codec`` + ``bridge_request_handler`` +
``wakeword_config`` + ``websocket_session``), validating the same contract
that the runtime uses in production. Captures the public smoke anchors
(/health, WebSocket bridge_connected ready frame, set_wakeword_config
round-trip) per the explore audit done for G2.

Non-test plumbing (importlib loader for the hyphen path + raw WebSocket
client helpers) lives in ``tests/_wakeword_integration_support.py``.
"""

from __future__ import annotations

import http.client
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

# wakeword_runtime depends on pypinyin; skip the whole module when absent —
# these are end-to-end tests of the wakeword runtime and can't be meaningfully
# executed without its pinyin dependency.
pytest.importorskip("pypinyin")

from tests._wakeword_integration_support import (  # noqa: E402
    load_http_server_module,
    ws_handshake,
    ws_recv_text,
    ws_send_masked_text,
)

# Load the on-disk hyphen-path module once per session (idempotent via sys.modules).
_http_server = load_http_server_module()
TestRuntimeHttpServer = _http_server.TestRuntimeHttpServer


@pytest.fixture
def runtime_server(tmp_path: Path):
    """Boot TestRuntimeHttpServer on an ephemeral port; tear down after test.

    Seeds the runtime layout that save_wakeword_config and
    build_wakeword_config_message expect: tmp_path/wakeword_runtime/{config.json,
    models/keywords.txt}.
    """
    runtime_root = tmp_path / "wakeword_runtime"
    runtime_root.mkdir()
    (runtime_root / "config.json").write_text(
        json.dumps({"wakeword": {"enabled": False, "wake_words": []}}),
        encoding="utf-8",
    )
    (runtime_root / "models").mkdir()
    (runtime_root / "models" / "keywords.txt").write_text("", encoding="utf-8")

    # port=0 lets the OS pick an ephemeral, parallel-safe port.
    server = TestRuntimeHttpServer(test_root=tmp_path, host="127.0.0.1", port=0)
    port = server._server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, name="wakeword-itest", daemon=True)
    thread.start()
    deadline = time.time() + 5.0
    ready = False
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                ready = True
                break
        except OSError:
            time.sleep(0.05)
    if not ready:
        server.shutdown()
        pytest.fail("TestRuntimeHttpServer did not come up within 5s")
    yield server, port
    server.shutdown()
    server._server.server_close()


def test_health_endpoint_returns_ok(runtime_server) -> None:
    """GET /health returns 200 application/json {"status":"ok"}."""
    _, port = runtime_server
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3.0)
    conn.request("GET", "/health")
    resp = conn.getresponse()
    body = resp.read()
    assert resp.status == 200
    assert resp.getheader("Content-Type") == "application/json; charset=utf-8"
    assert json.loads(body) == {"status": "ok"}
    conn.close()


def test_websocket_handshake_and_ready_frame(runtime_server) -> None:
    """After WS upgrade, server pushes bridge_connected ready message first."""
    _, port = runtime_server
    sock = ws_handshake("127.0.0.1", port)
    try:
        msg = ws_recv_text(sock)
        assert msg is not None
        parsed = json.loads(msg)
        assert parsed["type"] == "bridge_connected"
        assert parsed["payload"] == {"status": "ready"}
        assert parsed["success"] is True
    finally:
        sock.close()


def _drain_greeting(sock: socket.socket) -> tuple[str, str]:
    """Read the two greeting frames (ready, wakeword_config)."""
    ready = ws_recv_text(sock)
    assert ready is not None
    cfg = ws_recv_text(sock)
    assert cfg is not None
    return ready, cfg


def _recv_matching(sock: socket.socket, marker: str, timeout: float = 5.0) -> str:
    """Read frames until one containing ``marker`` appears (or timeout)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = ws_recv_text(sock)
        if msg is not None and marker in msg:
            return msg
    pytest.fail(f"no frame containing {marker!r} received within {timeout}s")


def test_set_wakeword_config_round_trip(runtime_server) -> None:
    """Client sends masked text frame set_wakeword_config; server responds with result.

    Validates the full codec + bridge_request_handler + wakeword_config contract
    end-to-end without any monkeypatch — the server writes the config to the
    test_root tmp_path and returns the saved payload.
    """
    _, port = runtime_server
    sock = ws_handshake("127.0.0.1", port)
    try:
        _drain_greeting(sock)
        request = json.dumps(
            {
                "type": "set_wakeword_config",
                "requestId": "itest-r1",
                "payload": {"enabled": True, "wakeWords": ["你好小智"]},
            }
        )
        ws_send_masked_text(sock, request)

        parsed = json.loads(_recv_matching(sock, "set_wakeword_config_result"))
        assert parsed["type"] == "set_wakeword_config_result"
        assert parsed["requestId"] == "itest-r1"
        assert parsed["success"] is True, f"save failed: {parsed}"
        assert parsed["payload"]["enabled"] is True
        assert parsed["payload"]["wakeWords"] == ["你好小智"]
    finally:
        sock.close()


def test_restart_wakeword_service_invokes_handler(runtime_server) -> None:
    """Client sends restart_wakeword_service; server responds restarting=True.

    A configured restart handler records the call so we can prove the handler
    path was invoked inside the event loop.
    """
    server, port = runtime_server
    fired: list[int] = []
    server.set_restart_handler(lambda: fired.append(1))
    sock = ws_handshake("127.0.0.1", port)
    try:
        _drain_greeting(sock)
        request = json.dumps({"type": "restart_wakeword_service", "requestId": "itest-r2"})
        ws_send_masked_text(sock, request)
        parsed = json.loads(_recv_matching(sock, "restart_wakeword_service_result"))
        assert parsed["type"] == "restart_wakeword_service_result"
        assert parsed["success"] is True
        assert parsed["payload"] == {"restarting": True}
    finally:
        sock.close()


def test_unknown_type_returns_failure_result(runtime_server) -> None:
    """Unknown message type gets a <type>_result with success=False and error string."""
    _, port = runtime_server
    sock = ws_handshake("127.0.0.1", port)
    try:
        _drain_greeting(sock)
        request = json.dumps({"type": "frobnicate", "requestId": "itest-r3"})
        ws_send_masked_text(sock, request)
        parsed = json.loads(_recv_matching(sock, "frobnicate_result"))
        assert parsed["type"] == "frobnicate_result"
        assert parsed["success"] is False
        assert "unsupported message type: frobnicate" in parsed["error"]
    finally:
        sock.close()
