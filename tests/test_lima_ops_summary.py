"""Test summary mode for lima-ops MCP (no SSH needed)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_OPS_PATH = Path(__file__).resolve().parents[1] / "lima_mcp_stdio" / "lima_ops_mcp.py"


def _mock_run_ssh(host: str, cmd: str, timeout: int = 10) -> str | None:
    """Return canned SSH responses so summary tools produce non-empty output."""
    if "uptime" in cmd:
        return "10 days"
    if "free" in cmd:
        return "mem:1G/2G"
    if "top" in cmd:
        return "cpu:5.0%"
    if "ps" in cmd and "wc" in cmd:
        return "1"
    if "VERSION" in cmd:
        return "v1.0"
    if "docker" in cmd and "wc" in cmd:
        return "0"
    if "ss -tnp" in cmd:
        return "0"
    if "curl" in cmd and ("health" in cmd or "models" in cmd or "device" in cmd):
        return "200"
    return None


@pytest.fixture
def ops_mod(monkeypatch):
    spec = importlib.util.spec_from_file_location("ops_mcp", _OPS_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "run_ssh", _mock_run_ssh)
    monkeypatch.setattr(mod, "get_servers", lambda: {"test": {"host": "127.0.0.1", "label": "test"}})
    return mod


def test_server_status_summary(ops_mod):
    summary = ops_mod.tool_server_status(summary=True, run_ssh=ops_mod.run_ssh, servers=ops_mod.get_servers())
    assert "===" not in summary
    assert "[test]" in summary
    assert "uptime:" in summary


def test_health_check_summary(ops_mod):
    summary = ops_mod.tool_health_check(summary=True, run_ssh=ops_mod.run_ssh, servers=ops_mod.get_servers())
    assert "===" not in summary
    assert "ok:" in summary


def test_device_connections_summary(ops_mod):
    summary = ops_mod.tool_device_connections(summary=True)
    assert "===" not in summary


def test_tail_log_summary(ops_mod):
    summary = ops_mod.tool_tail_log("app", summary=True)
    assert "===" not in summary
