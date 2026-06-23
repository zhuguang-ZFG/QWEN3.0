"""Tests for session_memory/processor.py — memory injection pipeline (P2-8 / P2-20)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from context_pipeline import RequestContext
from session_memory.processor import (
    _session_id_from_headers,
    save_request_memory,
    session_memory_processor,
)


def _memory(id_: int, summary: str, role: str = "exchange"):
    from session_memory.store import MemoryEntry

    return MemoryEntry(
        id=id_,
        session_id="sid",
        timestamp=0.0,
        role=role,
        summary=summary,
        detail="",
        embedding=[],
    )


@pytest.fixture
def enabled_env(monkeypatch):
    from session_memory import processor as proc_mod

    monkeypatch.setattr(proc_mod.SESSION_MEMORY, "enabled", True)


@pytest.fixture
def disabled_env(monkeypatch):
    from session_memory import processor as proc_mod

    monkeypatch.setattr(proc_mod.SESSION_MEMORY, "enabled", False)


def test_processor_disabled_returns_ctx_immediately(disabled_env):
    ctx = RequestContext(messages=[{"role": "user", "content": "hi"}])
    result = session_memory_processor(ctx)
    assert result is ctx
    assert result.system_prompt == ""


def test_processor_no_user_query_returns_ctx(enabled_env):
    ctx = RequestContext(messages=[{"role": "system", "content": "sys"}])
    result = session_memory_processor(ctx)
    assert result is ctx
    assert result.recalled_memory_ids == []


def test_session_id_is_stable():
    headers = {"x-forwarded-for": "1.2.3.4", "user-agent": "test"}
    assert _session_id_from_headers(headers) == _session_id_from_headers(headers)


def test_session_id_differs_with_headers():
    a = _session_id_from_headers({"x-forwarded-for": "1.2.3.4"})
    b = _session_id_from_headers({"x-forwarded-for": "5.6.7.8"})
    assert a != b


def test_processor_uses_keyword_search(enabled_env, monkeypatch):
    mem = _memory(1, "previous summary")
    monkeypatch.setattr(
        "session_memory.processor.search_memories_keyword",
        lambda sid, query, limit: [mem],
    )
    ctx = RequestContext(
        headers={"x-real-ip": "1.1.1.1"},
        messages=[{"role": "user", "content": "hello"}],
    )
    result = session_memory_processor(ctx)
    assert "previous summary" in result.system_prompt
    assert result.recalled_memory_ids == [1]


def test_processor_falls_back_to_semantic(enabled_env, monkeypatch):
    mem = _memory(2, "semantic hit")
    monkeypatch.setattr(
        "session_memory.processor.search_memories_keyword",
        lambda sid, query, limit: [],
    )
    monkeypatch.setattr(
        "session_memory.processor._semantic_fallback",
        lambda sid, query, limit: [mem],
    )

    ctx = RequestContext(
        headers={},
        messages=[{"role": "user", "content": "query"}],
    )
    result = session_memory_processor(ctx)
    assert "semantic hit" in result.system_prompt
    assert result.recalled_memory_ids == [2]


def test_processor_falls_back_to_cross_session(enabled_env, monkeypatch):
    mem = _memory(3, "global memory")
    monkeypatch.setattr(
        "session_memory.processor.search_memories_keyword",
        lambda sid, query, limit: [],
    )
    monkeypatch.setattr(
        "session_memory.processor._semantic_fallback",
        lambda sid, query, limit: [],
    )
    monkeypatch.setattr(
        "session_memory.processor._cross_session_fallback",
        lambda query, limit: [mem],
    )

    ctx = RequestContext(
        headers={},
        messages=[{"role": "user", "content": "query"}],
    )
    result = session_memory_processor(ctx)
    assert "global memory" in result.system_prompt
    assert result.recalled_memory_ids == [3]


def test_processor_falls_back_to_recent(enabled_env, monkeypatch):
    mem = _memory(4, "recent")
    monkeypatch.setattr(
        "session_memory.processor.search_memories_keyword",
        lambda sid, query, limit: [],
    )
    monkeypatch.setattr(
        "session_memory.processor._semantic_fallback",
        lambda sid, query, limit: [],
    )
    monkeypatch.setattr(
        "session_memory.processor._cross_session_fallback",
        lambda query, limit: [],
    )
    monkeypatch.setattr(
        "session_memory.processor.get_recent_memories",
        lambda sid, limit: [mem],
    )

    ctx = RequestContext(
        headers={},
        messages=[{"role": "user", "content": "query"}],
    )
    result = session_memory_processor(ctx)
    assert "recent" in result.system_prompt
    assert result.recalled_memory_ids == [4]


def test_processor_appends_to_existing_system_prompt(enabled_env, monkeypatch):
    mem = _memory(5, "mem")
    monkeypatch.setattr(
        "session_memory.processor.search_memories_keyword",
        lambda sid, query, limit: [mem],
    )
    ctx = RequestContext(
        headers={},
        messages=[{"role": "user", "content": "q"}],
        system_prompt="base",
    )
    result = session_memory_processor(ctx)
    assert result.system_prompt.startswith("base\n\n[session memory]")


def test_save_request_memory_disabled(disabled_env):
    with patch("session_memory.embeddings.save_memory_with_embedding") as mock_save:
        save_request_memory({}, [{"role": "user", "content": "hello"}])
    mock_save.assert_not_called()


def test_save_request_memory_enabled(enabled_env):
    with patch("session_memory.embeddings.save_memory_with_embedding") as mock_save:
        save_request_memory(
            {"x-real-ip": "1.1.1.1"},
            [{"role": "user", "content": "hello world"}],
            "response summary",
        )
    mock_save.assert_called_once()
    call = mock_save.call_args.kwargs
    assert call["session_id"] == _session_id_from_headers({"x-real-ip": "1.1.1.1"})
    assert "hello world" in call["summary"]
    assert "response summary" in call["summary"]
