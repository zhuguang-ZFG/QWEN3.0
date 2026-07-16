"""MCP must not turn dlc_api HTTP failures into successful tool results."""

from __future__ import annotations

import pytest
import httpx

from dlc_mcp.server import handle_request


class _Client:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    def post(self, *_args, **_kwargs):
        return self.response

    def get(self, *_args, **_kwargs):
        return self.response


def _call(client, name: str) -> dict:
    arguments = {"device_id": "dev-1"}
    if name == "dlc.write_text":
        arguments["text"] = "hello"
    return handle_request(
        client,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    )


@pytest.mark.parametrize("status", [401, 403, 422, 500])
@pytest.mark.parametrize("tool", ["dlc.write_text", "dlc.get_device_status"])
def test_http_error_becomes_mcp_error(status: int, tool: str) -> None:
    response = _call(_Client(httpx.Response(status, json={"detail": "Not authenticated"})), tool)
    assert response["error"]["code"] == -32603
    assert f"HTTP {status}" in response["error"]["message"]
    assert "任务已提交" not in str(response)


@pytest.mark.parametrize("tool", ["dlc.write_text", "dlc.get_device_status"])
def test_non_json_gateway_error_becomes_mcp_error(tool: str) -> None:
    response = _call(_Client(httpx.Response(502, text="proxy failure")), tool)
    assert response["error"]["message"] == "dlc_api HTTP 502"
