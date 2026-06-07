"""Tests for backward compatibility of legacy MCP endpoints — Task 6."""
from __future__ import annotations

import pytest
from unittest.mock import patch


def test_legacy_server_module_imports():
    """The legacy lima_mcp.server module must still import successfully."""
    from lima_mcp.server import router
    assert router is not None


def test_legacy_router_has_tools_list_endpoint():
    """Legacy router must have GET /tools/list endpoint (under /mcp prefix)."""
    from lima_mcp.server import router
    paths = [r.path for r in router.routes]
    assert "/mcp/tools/list" in paths


def test_legacy_router_has_tools_call_endpoint():
    """Legacy router must have POST /tools/call endpoint (under /mcp prefix)."""
    from lima_mcp.server import router
    paths = [r.path for r in router.routes]
    assert "/mcp/tools/call" in paths


def test_legacy_list_tools_returns_deprecation_header():
    """Legacy /tools/list response must include X-LiMa-Deprecation header."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from lima_mcp.server import router
    import os

    os.environ["LIMA_API_KEY"] = "test-key-for-mcp"
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.get("/mcp/tools/list", headers={"Authorization": "Bearer test-key-for-mcp"})
    assert resp.status_code == 200
    assert "X-LiMa-Deprecation" in resp.headers
    assert "deprecated" in resp.headers["X-LiMa-Deprecation"].lower()
    assert resp.headers.get("X-LiMa-Migrate-To") == "/v2/mcp"

    os.environ.pop("LIMA_API_KEY", None)


def test_legacy_call_tool_returns_deprecation_header():
    """Legacy /tools/call response must include X-LiMa-Deprecation header."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from lima_mcp.server import router
    import os

    os.environ["LIMA_API_KEY"] = "test-key-for-mcp"
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    with patch("lima_mcp.tools.handle_tool_call", return_value={"ok": True}):
        resp = client.post(
            "/mcp/tools/call",
            json={"name": "search_repo", "arguments": {"query": "test"}},
            headers={"Authorization": "Bearer test-key-for-mcp"},
        )
    assert resp.status_code == 200
    assert "X-LiMa-Deprecation" in resp.headers
    assert resp.headers.get("X-LiMa-Migrate-To") == "/v2/mcp"

    os.environ.pop("LIMA_API_KEY", None)


def test_legacy_and_new_coexist():
    """Both legacy router and new FastMCP server can be loaded together."""
    from lima_mcp.server import router as legacy_router
    from lima_mcp.fastmcp_server import mcp as new_mcp

    assert legacy_router is not None
    assert new_mcp is not None

    # New server should have more tools than legacy
    from lima_mcp.tool_defs import TOOL_DEFINITIONS
    new_tools = new_mcp._tool_manager.list_tools()
    assert len(new_tools) >= len(TOOL_DEFINITIONS) + 1  # +1 for health_check
