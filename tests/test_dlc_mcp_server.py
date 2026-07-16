"""Tests for dlc_mcp JSON-RPC server."""

from __future__ import annotations

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
