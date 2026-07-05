"""P1 security hardening: (a) disable /docs & /redoc, (b) avoid leaking intranet
host:port via dlc_mcp error messages.

These endpoints/tools are reachable from the public chat entrypoint. /docs and
/redoc must be disabled so attackers cannot enumerate the API surface. MCP tool
errors must not echo internal httpx exceptions (which carry 127.0.0.1:8081) back
to external callers.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx

from dlc_api.app import app as dlc_app
from dlc_mcp import server as mcp_server
from server_dlc import app as server_dlc_app


# ── /docs & /redoc disabled ───────────────────────────────────────────────────


def test_dlc_app_docs_disabled():
    assert dlc_app.docs_url is None
    assert dlc_app.redoc_url is None
    assert dlc_app.openapi_url is None


def test_server_dlc_docs_disabled():
    assert server_dlc_app.docs_url is None
    assert server_dlc_app.redoc_url is None
    assert server_dlc_app.openapi_url is None


# ── dlc_mcp error messages must not leak intranet host:port ────────────────────


def _conn_error(*_args, **_kwargs):
    raise httpx.ConnectError("[Errno 111] Connect call failed ('127.0.0.1', 8081)")


def test_mcp_submit_error_does_not_leak_intranet():
    """When dlc_api is unreachable, the returned error must be a generic
    message and must NOT contain the internal host/port."""
    client = httpx.Client()
    with patch.object(client, "post", side_effect=_conn_error):
        result = mcp_server._submit(client, "/dlc/tasks/preview", {"x": 1})
    assert result["status"] == "failed"
    err = result["error"]
    assert "127.0.0.1" not in err
    assert "8081" not in err


def test_mcp_get_json_error_does_not_leak_intranet():
    client = httpx.Client()
    with patch.object(client, "get", side_effect=_conn_error):
        result = mcp_server._get_json(client, "/dlc/status")
    err = result["error"]
    assert "127.0.0.1" not in err
    assert "8081" not in err
