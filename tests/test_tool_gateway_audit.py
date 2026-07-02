"""Tests for tool_gateway.audit."""

from __future__ import annotations

import os
import tempfile

import pytest

from config.sqlite_pool import pool_clear
from tool_gateway.audit import (
    _is_sensitive_key,
    _sanitize_text,
    _sanitize_value,
    audit_event,
    count_events,
    get_recent_events,
    query_events,
    reset_audit,
)


@pytest.fixture(autouse=True)
def isolated_audit_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point audit storage at a temporary SQLite DB and reset in-memory state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "audit.db")
        monkeypatch.setenv("LIMA_AUDIT_DB", db_path)
        reset_audit()
        yield
        reset_audit()
        pool_clear()


class TestSanitize:
    def test_is_sensitive_key_matches_substrings(self) -> None:
        assert _is_sensitive_key("api_key") is True
        assert _is_sensitive_key("MY_PASSWORD") is True
        assert _is_sensitive_key("authorization") is True
        assert _is_sensitive_key("username") is False

    def test_sanitize_text_redacts_bearer(self) -> None:
        # The session_memory redactor replaces only the secret portion.
        assert _sanitize_text("header: Bearer abc123xyz7890123456789") == "header: [REDACTED]"

    def test_sanitize_text_redacts_sk_token(self) -> None:
        assert _sanitize_text("sk-1234567890abcdefghijklmnopqrst") == "[REDACTED]"

    def test_sanitize_text_keeps_plain_text(self) -> None:
        assert _sanitize_text("hello world") == "hello world"

    def test_sanitize_value_redacts_sensitive_dict_keys(self) -> None:
        result = _sanitize_value({"username": "alice", "password": "secret"})
        assert result == {"username": "alice", "password": "[REDACTED]"}

    def test_sanitize_value_truncates_long_lists(self) -> None:
        result = _sanitize_value(list(range(60)))
        assert len(result) == 50

    def test_sanitize_value_leaves_primitives(self) -> None:
        assert _sanitize_value(42) == 42
        assert _sanitize_value(3.14) == 3.14
        assert _sanitize_value(True) is True
        assert _sanitize_value(None) is None


class TestAuditEvent:
    def test_audit_event_records_in_memory(self) -> None:
        reset_audit()
        event = audit_event("test", tool="hammer", reason="demo")
        assert event["event"] == "test"
        assert event["tool"] == "hammer"
        assert event["reason"] == "demo"
        assert "time" in event
        assert get_recent_events(limit=1)[0]["event"] == "test"

    def test_audit_event_persists_to_sqlite(self) -> None:
        reset_audit()
        audit_event("persist", tool="wrench")
        rows = query_events(event_type="persist")
        assert len(rows) == 1
        assert rows[0]["event"] == "persist"
        assert rows[0]["tool"] == "wrench"

    def test_audit_event_sanitizes_sensitive_fields(self) -> None:
        reset_audit()
        audit_event("login", token="secret-value")
        rows = query_events(event_type="login")
        assert rows[0]["details"]["token"] == "[REDACTED]"

    def test_in_memory_buffer_drops_old_events(self) -> None:
        reset_audit()
        for i in range(1100):
            audit_event("flood", seq=i)
        # After crossing 1000 events the buffer is trimmed to the last 500,
        # then 99 more events are appended -> 599 total in memory.
        recent = get_recent_events(limit=600)
        assert len(recent) == 599
        assert recent[0]["seq"] == 501
        capped = get_recent_events(limit=100)
        assert len(capped) == 100
        assert capped[0]["seq"] == 1000


class TestQueryAndCount:
    def test_query_filters_by_event_type(self) -> None:
        reset_audit()
        audit_event("type_a")
        audit_event("type_b")
        audit_event("type_a")
        assert len(query_events(event_type="type_a")) == 2
        assert len(query_events(event_type="type_b")) == 1

    def test_query_filters_by_tool(self) -> None:
        reset_audit()
        audit_event("run", tool="t1")
        audit_event("run", tool="t2")
        assert len(query_events(tool="t1")) == 1

    def test_query_limits_results(self) -> None:
        reset_audit()
        for _ in range(10):
            audit_event("bulk")
        assert len(query_events(event_type="bulk", limit=3)) == 3

    def test_count_events_returns_total(self) -> None:
        reset_audit()
        audit_event("countable")
        audit_event("countable")
        audit_event("other")
        assert count_events(event_type="countable") == 2
        assert count_events() == 3


class TestResetAudit:
    def test_reset_audit_clears_memory_and_db(self) -> None:
        reset_audit()
        audit_event("tmp")
        assert len(get_recent_events()) == 1
        assert count_events() == 1
        reset_audit()
        assert get_recent_events() == []
        assert count_events() == 0
