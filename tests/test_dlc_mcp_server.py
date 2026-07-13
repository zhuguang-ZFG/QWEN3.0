"""Tests for dlc_mcp JSON-RPC server."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import httpx

from dlc_mcp.server import handle_request


def test_initialize() -> None:
    client = httpx.Client()
    response = handle_request(client, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert response["result"]["serverInfo"]["name"] == "dlc-mcp-p0"


def test_tools_list_exposes_write_and_draw() -> None:
    client = httpx.Client()
    response = handle_request(client, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = response["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert "dlc.write_text" in names
    assert "dlc.draw_generated" in names
    assert "dlc.draw_from_image" in names
    assert "dlc.get_device_status" in names


def test_tools_call_write_text_validates_args() -> None:
    client = httpx.Client()
    response = handle_request(
        client,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "dlc.write_text", "arguments": {"device_id": "", "text": "x"}},
        },
    )
    assert "error" in response
    assert response["error"]["code"] == -32602


def test_tools_call_draw_generated_validates_args() -> None:
    client = httpx.Client()
    response = handle_request(
        client,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "dlc.draw_generated", "arguments": {"device_id": "dev-1", "prompt": ""}},
        },
    )
    assert "error" in response
    assert response["error"]["code"] == -32602


def test_tools_call_unknown_method() -> None:
    client = httpx.Client()
    response = handle_request(client, {"jsonrpc": "2.0", "id": 5, "method": "foo/bar"})
    assert "error" in response
    assert response["error"]["code"] == -32601


def test_ping_returns_empty_result() -> None:
    """MCP spec: ping must return an empty result object, not an error.

    XiaoZhi sends periodic ping keepalives; replying with -32601 makes it treat
    the connection as protocol-violating and close it (~24s crash loop).
    """
    client = httpx.Client()
    response = handle_request(client, {"jsonrpc": "2.0", "id": 8, "method": "ping"})
    assert "error" not in response
    assert response["result"] == {}
    assert response["id"] == 8


def test_notifications_initialized_is_ignored() -> None:
    """Notifications carry no id and expect no response; handler must not error out."""
    client = httpx.Client()
    response = handle_request(client, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    # A notification (no id) must not produce a response that gets written back.
    assert response is None or response.get("id") is None


def test_tools_call_draw_from_image_validates_args() -> None:
    client = httpx.Client()
    response = handle_request(
        client,
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "dlc.draw_from_image", "arguments": {"device_id": "", "image_url": "x"}},
        },
    )
    assert "error" in response
    assert response["error"]["code"] == -32602


def test_tools_call_get_device_status_validates_args() -> None:
    client = httpx.Client()
    response = handle_request(
        client,
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "dlc.get_device_status", "arguments": {"device_id": ""}},
        },
    )
    assert "error" in response
    assert response["error"]["code"] == -32602


def test_tools_call_write_text_submits_to_api() -> None:
    mock_resp = httpx.Response(
        200,
        json={"status": "queued", "task_id": "t1", "queue_depth": 1, "error": None},
    )
    with patch("dlc_mcp.server.httpx.Client") as mock_client:
        mock_client.return_value.__enter__ = lambda self: self
        mock_client.return_value.__exit__ = lambda *args: None
        mock_client.return_value.post = lambda _url, json, headers=None: mock_resp
        response = handle_request(
            mock_client.return_value,
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "dlc.write_text",
                    "arguments": {"device_id": "dev-1", "text": "hello"},
                },
            },
        )
    assert "result" in response
    assert "queued" in response["result"]["content"][0]["text"]


def test_submit_includes_bearer_token_when_configured() -> None:
    """dispatch requests must carry Authorization: Bearer <token> when DLC_API_TOKEN is set.

    dlc_api /dlc/tasks/dispatch requires verify_dlc_api_token; a bare POST gets 401.
    """
    captured: dict = {}
    mock_resp = httpx.Response(200, json={"status": "queued", "task_id": "t1", "queue_depth": 1, "error": None})

    class _Recorder:
        def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            return mock_resp

    with patch("dlc_mcp.server.DLC_API_TOKEN", "secret-token"):
        handle_request(
            _Recorder(),
            {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {"name": "dlc.write_text", "arguments": {"device_id": "dev-1", "text": "hi"}},
            },
        )
    assert captured["headers"].get("Authorization") == "Bearer secret-token"


def test_get_status_includes_bearer_token_when_configured() -> None:
    """status queries must also carry the bearer token (endpoint is auth-guarded)."""
    captured: dict = {}
    mock_resp = httpx.Response(
        200,
        json={"device_id": "dev-1", "online": True, "working": False},
    )

    class _Recorder:
        def get(self, url, headers=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            return mock_resp

    with patch("dlc_mcp.server.DLC_API_TOKEN", "secret-token"):
        handle_request(
            _Recorder(),
            {
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {"name": "dlc.get_device_status", "arguments": {"device_id": "dev-1"}},
            },
        )
    assert captured["headers"].get("Authorization") == "Bearer secret-token"


def test_submit_includes_idempotency_key_for_dispatch() -> None:
    """dispatch POST must carry content-addressed Idempotency-Key: mcp-<32hex>."""
    keys: list[str] = []
    mock_resp = httpx.Response(200, json={"status": "queued", "task_id": "t1", "queue_depth": 1, "error": None})

    class _Recorder:
        def post(self, url, json=None, headers=None):
            keys.append((headers or {}).get("Idempotency-Key", ""))
            return mock_resp

    payload_args = {"device_id": "dev-1", "text": "hi"}
    for req_id in (30, 99):
        handle_request(
            _Recorder(),
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/call",
                "params": {"name": "dlc.write_text", "arguments": payload_args},
            },
        )
    assert len(keys) == 2
    for key in keys:
        assert re.fullmatch(r"mcp-[0-9a-f]{32}", key), key
    assert keys[0] == keys[1]

    # Canary: expected digest from the same content-addressing algorithm.
    endpoint = "/dlc/tasks/dispatch"
    body = {"type": "write_text", "device_id": "dev-1", "payload": {"text": "hi"}}
    canonical = json.dumps(
        {"e": endpoint, "p": body},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    expected = "mcp-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    assert keys[0] == expected


def test_idempotency_key_differs_for_different_payload() -> None:
    """Different write_text content must produce different Idempotency-Key values."""
    keys: list[str] = []
    mock_resp = httpx.Response(200, json={"status": "queued", "task_id": "t1", "queue_depth": 1, "error": None})

    class _Recorder:
        def post(self, url, json=None, headers=None):
            keys.append((headers or {}).get("Idempotency-Key", ""))
            return mock_resp

    for text in ("hi", "hello"):
        handle_request(
            _Recorder(),
            {
                "jsonrpc": "2.0",
                "id": 30,
                "method": "tools/call",
                "params": {"name": "dlc.write_text", "arguments": {"device_id": "dev-1", "text": text}},
            },
        )
    assert len(keys) == 2
    assert re.fullmatch(r"mcp-[0-9a-f]{32}", keys[0])
    assert re.fullmatch(r"mcp-[0-9a-f]{32}", keys[1])
    assert keys[0] != keys[1]


def test_submit_omits_auth_header_when_no_token() -> None:
    """No DLC_API_TOKEN → no Authorization header (dev/local behavior unchanged)."""
    captured: dict = {}
    mock_resp = httpx.Response(200, json={"status": "queued", "task_id": "t1", "queue_depth": 1, "error": None})

    class _Recorder:
        def post(self, url, json=None, headers=None):
            captured["headers"] = headers or {}
            return mock_resp

    with patch("dlc_mcp.server.DLC_API_TOKEN", ""):
        handle_request(
            _Recorder(),
            {
                "jsonrpc": "2.0",
                "id": 22,
                "method": "tools/call",
                "params": {"name": "dlc.write_text", "arguments": {"device_id": "dev-1", "text": "hi"}},
            },
        )
    assert "Authorization" not in captured["headers"]


def test_main_stdout_is_valid_utf8_json() -> None:
    """Ensure JSON-RPC lines are emitted as UTF-8 bytes even on Windows (GBK) console."""
    server_path = Path(__file__).resolve().parents[1] / "dlc_mcp" / "server.py"
    proc = subprocess.Popen(
        [sys.executable, str(server_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    req = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/list"}) + "\n"
    stdout, stderr = proc.communicate(req.encode("utf-8"), timeout=5)
    assert proc.returncode == 0
    assert not stderr
    # Verify raw bytes are valid UTF-8 (would fail if console defaulted to GBK).
    line = stdout.decode("utf-8")
    resp = json.loads(line)
    assert resp["id"] == 7
    names = {tool["name"] for tool in resp["result"]["tools"]}
    assert "dlc.write_text" in names
