"""Tests for dlc_mcp JSON-RPC server."""

from __future__ import annotations

import json
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


def test_tools_call_write_text_submits_to_api() -> None:
    mock_resp = httpx.Response(
        200,
        json={"status": "queued", "task_id": "t1", "queue_depth": 1, "error": None},
    )
    with patch("dlc_mcp.server.httpx.Client") as mock_client:
        mock_client.return_value.__enter__ = lambda self: self
        mock_client.return_value.__exit__ = lambda *args: None
        mock_client.return_value.post = lambda _url, json: mock_resp
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
