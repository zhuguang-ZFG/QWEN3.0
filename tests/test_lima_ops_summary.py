"""Test summary mode for lima-ops MCP (no SSH needed)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_OPS_PATH = Path(__file__).resolve().parents[1] / "lima_mcp_stdio" / "lima_ops_mcp.py"


@pytest.fixture
def ops_mod(monkeypatch):
    spec = importlib.util.spec_from_file_location("ops_mcp", _OPS_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "run_ssh", lambda host, cmd, timeout=10: None)
    monkeypatch.setattr(mod, "get_servers", lambda: {"test": {"host": "127.0.0.1", "label": "test"}})
    return mod


def test_server_status_summary(ops_mod):
    summary = ops_mod.tool_server_status(summary=True)
    assert "===" not in summary
    assert "[test]" in summary
    assert "uptime:" in summary


def test_health_check_summary(ops_mod):
    summary = ops_mod.tool_health_check(summary=True)
    assert "===" not in summary
    assert "ok:" in summary


def test_device_connections_summary(ops_mod):
    summary = ops_mod.tool_device_connections(summary=True)
    assert "===" not in summary


def test_tail_log_summary(ops_mod):
    summary = ops_mod.tool_tail_log("app", summary=True)
    assert "===" not in summary
