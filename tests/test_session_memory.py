import os
import tempfile

import pytest

os.environ["LIMA_SESSION_DB"] = tempfile.mktemp(suffix=".db")
os.environ["LIMA_SESSION_MEMORY"] = "1"

from session_memory.store import (
    save_memory,
    get_recent_memories,
    search_memories_keyword,
    search_memories_semantic,
    count_memories,
    clear_session,
)
from session_memory.processor import (
    _session_id_from_headers,
    session_memory_processor,
    save_request_memory,
)
from context_pipeline import RequestContext


def test_save_and_retrieve_memory():
    sid = "test-session-1"
    entry_id = save_memory(sid, "exchange", "user asked about routing")
    assert entry_id > 0

    memories = get_recent_memories(sid, limit=5)
    assert len(memories) == 1
    assert memories[0].summary == "user asked about routing"
    assert memories[0].role == "exchange"


def test_keyword_search():
    sid = "test-session-2"
    save_memory(sid, "exchange", "fix bug in routing_engine.py")
    save_memory(sid, "exchange", "add embeddings endpoint")
    save_memory(sid, "exchange", "deploy to server")

    results = search_memories_keyword(sid, "routing", limit=3)
    assert len(results) == 1
    assert "routing" in results[0].summary


def test_semantic_search():
    sid = "test-session-3"
    save_memory(sid, "exchange", "routing logic", embedding=[0.9, 0.1, 0.0])
    save_memory(sid, "exchange", "health check", embedding=[0.1, 0.9, 0.0])

    results = search_memories_semantic(sid, [0.85, 0.15, 0.0], limit=2)
    assert len(results) == 2
    assert results[0].summary == "routing logic"


def test_semantic_search_skips_mismatched_embedding_dimensions():
    sid = "test-session-mismatch"
    save_memory(sid, "exchange", "short embedding", embedding=[1.0, 0.0])
    save_memory(sid, "exchange", "matching embedding", embedding=[0.9, 0.1, 0.0])

    results = search_memories_semantic(sid, [0.85, 0.15, 0.0], limit=5)

    assert [r.summary for r in results] == ["matching embedding"]


def test_count_and_clear():
    sid = "test-session-4"
    save_memory(sid, "exchange", "entry 1")
    save_memory(sid, "exchange", "entry 2")
    save_memory(sid, "exchange", "entry 3")

    assert count_memories(sid) == 3
    deleted = clear_session(sid)
    assert deleted == 3
    assert count_memories(sid) == 0


def test_session_id_from_headers():
    h1 = {"x-forwarded-for": "1.2.3.4", "user-agent": "opencode/1.0"}
    h2 = {"x-forwarded-for": "1.2.3.4", "user-agent": "opencode/1.0"}
    h3 = {"x-forwarded-for": "5.6.7.8", "user-agent": "opencode/2.0"}

    sid1 = _session_id_from_headers(h1)
    sid2 = _session_id_from_headers(h2)
    sid3 = _session_id_from_headers(h3)

    assert sid1 == sid2
    assert sid1 != sid3
    assert len(sid1) == 16


def test_session_memory_processor_injects_memories():
    sid = _session_id_from_headers({"x-forwarded-for": "10.0.0.1", "user-agent": "test"})
    save_memory(sid, "exchange", "fixed routing bug in routing_engine.py")

    ctx = RequestContext(
        headers={"x-forwarded-for": "10.0.0.1", "user-agent": "test"},
        messages=[{"role": "user", "content": "routing issue again"}],
        system_prompt="existing prompt",
    )
    ctx = session_memory_processor(ctx)

    assert "session memory" in ctx.system_prompt
    assert "routing" in ctx.system_prompt


def test_session_memory_processor_skipped_when_disabled():
    os.environ["LIMA_SESSION_MEMORY"] = "0"
    ctx = RequestContext(
        headers={"x-forwarded-for": "10.0.0.1", "user-agent": "test"},
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="original",
    )
    ctx = session_memory_processor(ctx)
    assert ctx.system_prompt == "original"
    os.environ["LIMA_SESSION_MEMORY"] = "1"


def test_save_request_memory():
    headers = {"x-forwarded-for": "20.0.0.1", "user-agent": "opencode"}
    messages = [{"role": "user", "content": "add embeddings endpoint to server.py"}]

    sid = _session_id_from_headers(headers)
    before = count_memories(sid)
    save_request_memory(headers, messages, response_summary="added /v1/embeddings")
    after = count_memories(sid)

    assert after == before + 1
    memories = get_recent_memories(sid, limit=1)
    assert "embeddings" in memories[0].summary
