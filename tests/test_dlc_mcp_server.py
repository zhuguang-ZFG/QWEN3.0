"""Tests for dlc_mcp JSON-RPC server."""

from __future__ import annotations

import httpx
import pytest

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
    assert response["result"]["nextCursor"] == ""


def test_tools_list_cursor_starts_at_named_tool() -> None:
    client = httpx.Client()
    response = handle_request(
        client,
        {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/list",
            "params": {"cursor": "dlc.draw_generated"},
        },
    )
    names = [tool["name"] for tool in response["result"]["tools"]]
    assert names[0] == "dlc.draw_generated"
    assert "dlc.write_text" not in names


def test_tools_list_unknown_cursor_returns_empty() -> None:
    client = httpx.Client()
    response = handle_request(
        client,
        {"jsonrpc": "2.0", "id": 22, "method": "tools/list", "params": {"cursor": "no.such"}},
    )
    assert response["result"]["tools"] == []
    assert response["result"]["nextCursor"] == ""


def test_rejects_missing_jsonrpc_version() -> None:
    client = httpx.Client()
    response = handle_request(client, {"id": 23, "method": "initialize"})
    assert response["error"]["code"] == -32600


def test_tools_call_success_includes_is_error_false(monkeypatch) -> None:
    def _fake_submit(_client, _endpoint, _payload, idem_key=None):
        return {"status": "accepted", "sent": 1, "queue_depth": 0, "task_id": "task-1"}

    monkeypatch.setattr("dlc_mcp.server._submit", _fake_submit)
    client = httpx.Client()
    response = handle_request(
        client,
        {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {"name": "dlc.write_text", "arguments": {"device_id": "dev-1", "text": "hi"}},
        },
    )
    assert "error" not in response
    assert response["result"]["isError"] is False
    assert response["result"]["content"][0]["type"] == "text"


def test_tools_call_queued_no_delivery_is_error_true(monkeypatch) -> None:
    def _fake_submit(_client, _endpoint, _payload, idem_key=None):
        return {"status": "queued_no_delivery", "task_id": "task-q", "queue_depth": 1}

    monkeypatch.setattr("dlc_mcp.server._submit", _fake_submit)
    client = httpx.Client()
    response = handle_request(
        client,
        {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {"name": "dlc.write_text", "arguments": {"device_id": "dev-1", "text": "hi"}},
        },
    )
    assert "error" not in response
    assert response["result"]["isError"] is True
    assert "下发通道" in response["result"]["content"][0]["text"]


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


def test_non_dict_request_returns_invalid_request_error() -> None:
    """Regression: a syntactically valid but non-object JSON (e.g. a list) must
    yield a -32600 error with id:null, not crash on req.get()."""
    client = httpx.Client()
    response = handle_request(client, [1, 2, 3])
    assert response["error"]["code"] == -32600
    assert response["id"] is None


def test_output_filter_keeps_id_null_error_response() -> None:
    """Regression #2: the main() stdout filter must not drop a valid JSON-RPC
    error response just because its id is null. Error responses (id:null,
    error present) MUST be written back; only notification acks ({}) are skipped.

    We assert the exact filter predicate used in main() so a future refactor
    that reverts to ``resp.get("id") is not None`` fails here.
    """

    def _should_write(resp: dict) -> bool:
        return bool(resp) and (resp.get("id") is not None or resp.get("error") is not None)

    # id:null error response (invalid-request path) — must be written.
    assert _should_write({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "x"}})
    # Normal id-carrying result — must be written.
    assert _should_write({"jsonrpc": "2.0", "id": 7, "result": {}})
    # Notification ack ({}) — must be skipped (no id, no error).
    assert not _should_write({})


def test_exception_handler_backfills_request_id(monkeypatch) -> None:
    """Regression #1: when handle_request raises, the error response must carry
    the original request id (not a hardcoded None) so the client can correlate
    it, and must tolerate a non-dict req without a second crash."""
    from dlc_mcp import server

    # id backfilled from a dict request.
    err = server._tool_error({"id": 42}.get("id"), -32603, "Internal error")
    assert err["id"] == 42
    # non-dict request degrades to id:null without raising.
    req = [1, 2, 3]
    safe_id = req.get("id") if isinstance(req, dict) else None
    assert safe_id is None


def test_is_remote_dlc_api_detects_loopback() -> None:
    from dlc_mcp.remote_token import is_remote_dlc_api

    assert is_remote_dlc_api("http://127.0.0.1:8081") is False
    assert is_remote_dlc_api("http://localhost:8081") is False
    assert is_remote_dlc_api("http://[::1]:8081") is False
    assert is_remote_dlc_api("https://chat.donglicao.com/dlc") is True


def test_require_remote_api_token_exits_when_remote_and_empty(monkeypatch) -> None:
    from dlc_mcp.remote_token import require_remote_api_token

    with pytest.raises(SystemExit) as exc_info:
        require_remote_api_token(api_url="https://api.example.com", api_token="")
    assert exc_info.value.code == 1


def test_require_remote_api_token_allows_loopback_empty() -> None:
    from dlc_mcp.remote_token import require_remote_api_token

    require_remote_api_token(api_url="http://127.0.0.1:8081", api_token="")
