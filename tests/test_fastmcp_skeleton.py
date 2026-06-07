"""Tests for FastMCP server skeleton — Task 1."""
from __future__ import annotations

import pytest


def test_mcp_sdk_importable():
    """The mcp package must be installed and importable."""
    from mcp.server.fastmcp import FastMCP
    assert FastMCP is not None


def test_fastmcp_server_module_importable():
    """lima_mcp.fastmcp_server must import without errors."""
    from lima_mcp.fastmcp_server import mcp
    assert mcp is not None


def test_fastmcp_server_name():
    """FastMCP instance must be named 'LiMa'."""
    from lima_mcp.fastmcp_server import mcp
    assert mcp.name == "LiMa"


def test_health_check_tool_registered():
    """A 'health_check' tool must be registered on the FastMCP instance."""
    from lima_mcp.fastmcp_server import mcp
    tool_names = [tool.name for tool in mcp._tool_manager.list_tools()]
    assert "health_check" in tool_names


def test_health_check_tool_returns_ok():
    """Calling health_check must return a dict with ok=True."""
    from lima_mcp.fastmcp_server import health_check
    result = health_check()
    assert result["ok"] is True
    assert "version" in result
    assert "timestamp" in result
