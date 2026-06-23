"""Regression tests for routing_engine_context.py warning logs (P1-3)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import routing_engine_context as rec


@pytest.fixture(autouse=True)
def _clear_import_side_effects():
    """Ensure each test starts with a clean module state."""
    yield


def test_inject_coding_context_logs_code_context_failure(monkeypatch, caplog):
    def raise_exc(*args, **kwargs):
        raise RuntimeError("scan failed")

    monkeypatch.setattr("context_pipeline.code_context_injection.scan_and_build_context", raise_exc)
    messages = [{"role": "user", "content": "hi"}]
    result, ctx = rec.inject_coding_context(messages, "coding", "query")
    assert result is messages
    assert ctx == ""
    assert any("code_context_injection failed" in m for m in caplog.messages)


def test_inject_coding_context_logs_memory_failure(monkeypatch, caplog):
    def raise_exc(*args, **kwargs):
        raise RuntimeError("memory failed")

    monkeypatch.setattr("session_memory.store_promote.query_by_type", raise_exc)
    messages = [{"role": "user", "content": "hi"}]
    result, ctx = rec.inject_coding_context(messages, "coding", "query")
    assert result is messages
    assert any("memory promote failed" in m for m in caplog.messages)


def test_assess_complexity_logs_exception(monkeypatch, caplog):
    def raise_exc(*args, **kwargs):
        raise RuntimeError("complexity failed")

    monkeypatch.setattr("context_pipeline.complexity.assess_complexity", raise_exc)
    assert rec.assess_complexity([{"role": "user", "content": "hi"}], "vscode") is None
    assert any("complexity assessment failed" in m for m in caplog.messages)


def test_auto_compress_logs_import_error(caplog):
    """Missing context_compressor should be logged as a warning, not crash."""
    with patch.dict("sys.modules", {"context_compressor": None}):
        messages = [{"role": "user", "content": "hi"}]
        result = rec.auto_compress(messages, ["backend"], "sys prompt")
    assert result is messages
