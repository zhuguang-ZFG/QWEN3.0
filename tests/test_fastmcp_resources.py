"""Tests for FastMCP resources — Task 3."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import json
import pytest


def test_backend_health_resource_registered():
    """resource://lima/backends/health must be registered."""
    from lima_mcp.fastmcp_server import mcp
    resources = mcp._resource_manager.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "resource://lima/backends/health" in uris


def test_stats_resource_registered():
    """resource://lima/stats must be registered."""
    from lima_mcp.fastmcp_server import mcp
    resources = mcp._resource_manager.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "resource://lima/stats" in uris


def test_routing_scores_resource_registered():
    """resource://lima/routing/scores must be registered."""
    from lima_mcp.fastmcp_server import mcp
    resources = mcp._resource_manager.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "resource://lima/routing/scores" in uris


def test_backend_health_resource_returns_json():
    """Reading backend health resource returns valid JSON."""
    from lima_mcp.fastmcp_server import get_backend_health

    with patch("lima_mcp.fastmcp_server._fetch_backend_statuses") as mock_fetch:
        mock_fetch.return_value = {
            "backends": {"cloudflare": {"status": "healthy", "latency_ms": 45}},
            "overall": "healthy",
        }
        result = get_backend_health()
        data = json.loads(result) if isinstance(result, str) else result
        assert "backends" in data
        assert data["overall"] == "healthy"


def test_stats_resource_returns_data():
    """Reading stats resource returns system statistics."""
    from lima_mcp.fastmcp_server import get_stats

    with patch("lima_mcp.fastmcp_server._fetch_system_stats") as mock_stats:
        mock_stats.return_value = {
            "uptime_seconds": 3600,
            "tools_registered": 36,
        }
        result = get_stats()
        data = json.loads(result) if isinstance(result, str) else result
        assert "uptime_seconds" in data
