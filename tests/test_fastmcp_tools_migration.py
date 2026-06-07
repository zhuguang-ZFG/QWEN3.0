"""Tests for migrated FastMCP tool definitions — Task 2."""
from __future__ import annotations

from unittest.mock import patch

import pytest

# Check if mcp module is available
try:
    import mcp.server.fastmcp
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not MCP_AVAILABLE,
    reason="mcp module not installed (install with: pip install 'mcp[cli]')"
)




def test_all_original_tools_registered():
    """Every tool from tool_defs.py must be registered on the FastMCP server."""
    from lima_mcp.fastmcp_server import mcp
    from lima_mcp.tool_defs import TOOL_DEFINITIONS

    registered_names = {tool.name for tool in mcp._tool_manager.list_tools()}
    expected_names = {td["name"] for td in TOOL_DEFINITIONS}

    # health_check from Task 1 is also present
    assert expected_names.issubset(registered_names), (
        f"Missing tools: {expected_names - registered_names}"
    )


def test_tool_count_matches():
    """FastMCP tool count >= tool_defs count (includes health_check)."""
    from lima_mcp.fastmcp_server import mcp
    from lima_mcp.tool_defs import TOOL_DEFINITIONS

    registered = mcp._tool_manager.list_tools()
    assert len(registered) >= len(TOOL_DEFINITIONS) + 1  # +1 for health_check


def test_search_repo_tool_has_correct_schema():
    """search_repo tool must preserve its original parameter schema."""
    from lima_mcp.fastmcp_server import mcp

    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    assert "search_repo" in tools
    schema = tools["search_repo"].parameters
    assert "query" in schema.get("properties", {})


def test_tool_call_dispatches_to_handler():
    """Calling a migrated tool must dispatch to the original handler in tools.py."""
    from lima_mcp.fastmcp_server import _dispatch_tool_call

    with patch("lima_mcp.tools.handle_tool_call") as mock_handler:
        mock_handler.return_value = {"results": [], "query_entities": ["test"]}
        result = _dispatch_tool_call("search_repo", {"query": "test", "max_results": 5})
        mock_handler.assert_called_once_with("search_repo", {"query": "test", "max_results": 5})
        assert result["results"] == []


def test_tool_call_unknown_returns_error():
    """Unknown tool name returns an error dict."""
    from lima_mcp.fastmcp_server import _dispatch_tool_call

    with patch("lima_mcp.tools.handle_tool_call", return_value={"error": "Unknown tool: nonexistent"}):
        result = _dispatch_tool_call("nonexistent", {})
        assert "error" in result
