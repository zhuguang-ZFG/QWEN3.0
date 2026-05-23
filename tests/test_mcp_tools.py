"""Tests for LiMa MCP tools."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_tool_definitions_structure():
    from lima_mcp import TOOL_DEFINITIONS
    assert len(TOOL_DEFINITIONS) == 3
    names = [t["name"] for t in TOOL_DEFINITIONS]
    assert "search_repo" in names
    assert "search_memory" in names
    assert "get_retrieval_trace" in names


def test_handle_unknown_tool():
    from lima_mcp.tools import handle_tool_call
    result = handle_tool_call("nonexistent", {})
    assert "error" in result


def test_search_repo_returns_results():
    from lima_mcp.tools import handle_tool_call
    result = handle_tool_call("search_repo", {"query": "routing_engine health_tracker"})
    assert "results" in result
    assert "query_entities" in result


def test_search_memory_returns_types_hint():
    from lima_mcp.tools import handle_tool_call
    result = handle_tool_call("search_memory", {})
    assert "available_types" in result


def test_get_retrieval_trace_returns_list():
    from lima_mcp.tools import handle_tool_call
    result = handle_tool_call("get_retrieval_trace", {"limit": 5})
    assert "traces" in result
    assert isinstance(result["traces"], list)
