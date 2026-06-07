"""Tests for FastMCP mount onto FastAPI -- Task 5."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


def test_mount_mcp_function_exists():
    """mount_mcp function must exist in fastmcp_server module."""
    from lima_mcp.fastmcp_server import mount_mcp
    assert callable(mount_mcp)


def test_mount_mcp_adds_sub_app():
    """mount_mcp must add a sub-application to the FastAPI app."""
    from fastapi import FastAPI
    from lima_mcp.fastmcp_server import mount_mcp

    test_app = FastAPI()
    initial_routes = len(test_app.routes)
    mount_mcp(test_app, path="/v2/mcp")

    # After mounting, there should be at least one additional route/mount
    assert len(test_app.routes) > initial_routes


def test_mount_mcp_custom_path():
    """mount_mcp should accept a custom path."""
    from fastapi import FastAPI
    from lima_mcp.fastmcp_server import mount_mcp

    test_app = FastAPI()
    mount_mcp(test_app, path="/custom/mcp/path")

    # Check that the mount exists with the custom path
    mount_paths = [r.path for r in test_app.routes if hasattr(r, 'path')]
    assert "/custom/mcp/path" in mount_paths


def test_streamable_http_app_returns_asgi():
    """The FastMCP streamable_http_app should return an ASGI application."""
    from lima_mcp.fastmcp_server import mcp

    asgi_app = mcp.streamable_http_app()
    assert callable(asgi_app)  # ASGI apps are callable


def test_mount_mcp_default_path():
    """mount_mcp should default to /v2/mcp when no path is given."""
    from fastapi import FastAPI
    from lima_mcp.fastmcp_server import mount_mcp
    import inspect

    sig = inspect.signature(mount_mcp)
    path_param = sig.parameters.get("path")
    assert path_param is not None
    assert path_param.default == "/v2/mcp"


def test_mount_mcp_sets_streamable_http_path():
    """mount_mcp must set streamable_http_path to '/' so endpoint is at mount root."""
    from fastapi import FastAPI
    from lima_mcp.fastmcp_server import mount_mcp, mcp

    test_app = FastAPI()
    mount_mcp(test_app, path="/v2/mcp")

    # After mounting, the internal streamable_http_path should be "/"
    # so the MCP endpoint is at /v2/mcp (not /v2/mcp/mcp)
    assert mcp.settings.streamable_http_path == "/"


def test_mount_mcp_does_not_conflict_with_old_mcp():
    """The /v2/mcp mount should not conflict with the old /mcp router."""
    from fastapi import FastAPI
    from lima_mcp.fastmcp_server import mount_mcp

    test_app = FastAPI()
    mount_mcp(test_app, path="/v2/mcp")

    # Collect all paths
    all_paths = [r.path for r in test_app.routes if hasattr(r, 'path')]
    # /v2/mcp should be present
    assert "/v2/mcp" in all_paths
    # /mcp should NOT be present (it's the old router, not added here)
    # This just verifies we didn't accidentally add a /mcp route
    assert "/mcp" not in all_paths
