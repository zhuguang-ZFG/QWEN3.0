"""Tests for codesearch adapter (LC-W-2)."""

from __future__ import annotations

from pathlib import Path

import search_gateway.codesearch_adapter as mod


def test_codesearch_disabled(monkeypatch):
    monkeypatch.setenv("CODESEARCH_MCP_ENABLED", "0")
    result = mod.search_local_code("routing_engine")
    assert result["ok"] is False
    assert result["error"] == "codesearch_disabled"


def test_codesearch_binary_missing(monkeypatch):
    monkeypatch.setenv("CODESEARCH_MCP_ENABLED", "1")
    monkeypatch.setattr(mod, "_binary", lambda: None)
    result = mod.search_local_code("routing_engine")
    assert result["error"] == "codesearch_binary_missing"


def test_path_not_in_allowlist(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODESEARCH_MCP_ENABLED", "1")
    monkeypatch.setenv("CODESEARCH_INDEX_PATHS", str(tmp_path))
    monkeypatch.setattr(mod, "_binary", lambda: "codesearch")
    result = mod.search_local_code("foo", path_hint="C:/outside")
    assert result["error"] == "path_not_in_allowlist"


def test_search_local_code_success(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODESEARCH_MCP_ENABLED", "1")
    monkeypatch.setenv("CODESEARCH_INDEX_PATHS", str(tmp_path))

    class Proc:
        returncode = 0
        stdout = '[{"path":"routes/github_webhook.py","snippet":"webhook"}]'
        stderr = ""

    monkeypatch.setattr(mod, "_binary", lambda: "codesearch")
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: Proc())
    result = mod.search_local_code("github webhook", path_hint=str(tmp_path))
    assert result["ok"] is True
    assert result["results"][0]["path"] == "routes/github_webhook.py"
