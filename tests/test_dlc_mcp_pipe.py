"""Tests for dlc_mcp.mcp_pipe helpers."""

from __future__ import annotations

from dlc_mcp.mcp_pipe import _default_server_cmd, _websocket_header_kwargs


def test_websocket_header_kwargs_supports_new_api() -> None:
    def connect(uri: str, *, additional_headers=None):
        return uri, additional_headers

    assert _websocket_header_kwargs(connect, {"Authorization": "Bearer x"}) == {
        "additional_headers": {"Authorization": "Bearer x"}
    }


def test_websocket_header_kwargs_supports_old_api() -> None:
    def connect(uri: str, *, extra_headers=None):
        return uri, extra_headers

    assert _websocket_header_kwargs(connect, {"Authorization": "Bearer x"}) == {
        "extra_headers": {"Authorization": "Bearer x"}
    }


def test_default_server_cmd_points_to_local_server() -> None:
    cmd = _default_server_cmd()
    assert cmd[0]
    assert cmd[1].endswith(("dlc_mcp/server.py", "dlc_mcp\\server.py"))
