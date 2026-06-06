"""Tests for LiMa MCP tools."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_tool_definitions_structure():
    from lima_mcp import TOOL_DEFINITIONS
    names = [t["name"] for t in TOOL_DEFINITIONS]
    assert "search_repo" in names
    assert "search_memory" in names
    assert "get_retrieval_trace" in names
    assert "dev_search_docs" in names


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


# ── Phase 0: MCP fail-closed regression ──────────────────────────────────────

def test_mcp_verify_rejects_when_no_token_configured(monkeypatch):
    """P1: MCP must fail-closed when no token is configured."""
    monkeypatch.setenv("LIMA_API_KEY", "")
    monkeypatch.setenv("LIMA_MCP_TOKEN", "")
    # Re-import to pick up patched env

    import lima_mcp.server as mcp_srv
    monkeypatch.setattr(mcp_srv, "_MCP_TOKEN", "")

    import asyncio

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(mcp_srv._verify_mcp_access(""))
    assert exc_info.value.status_code == 503


def test_mcp_verify_rejects_wrong_bearer(monkeypatch):
    """Wrong bearer token returns 401."""
    import lima_mcp.server as mcp_srv
    monkeypatch.setenv("LIMA_API_KEY", "")
    monkeypatch.setenv("LIMA_MCP_TOKEN", "")
    monkeypatch.setattr(mcp_srv, "_MCP_TOKEN", "correct-token")

    import asyncio

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(mcp_srv._verify_mcp_access("Bearer wrong-token"))
    assert exc_info.value.status_code == 401


def test_mcp_verify_passes_correct_bearer(monkeypatch):
    """Correct bearer token passes without exception."""
    import lima_mcp.server as mcp_srv
    monkeypatch.setenv("LIMA_API_KEY", "")
    monkeypatch.setenv("LIMA_MCP_TOKEN", "")
    monkeypatch.setattr(mcp_srv, "_MCP_TOKEN", "correct-token")

    import asyncio
    asyncio.run(mcp_srv._verify_mcp_access("Bearer correct-token"))
