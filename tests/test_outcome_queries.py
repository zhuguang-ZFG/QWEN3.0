"""Tests for session_memory/outcome_queries.py — ledger dict conversion."""

from session_memory.outcome_queries import _row_to_dict


class TestRowToDict:
    def test_basic_conversion(self):
        row = (
            "id-1",
            "test",
            "completion",
            "loop-1",
            "ok",
            "groq",
            "chat",
            "task-1",
            "device-1",
            "req-1",
            "chat",
            1,
            123,
            "summary",
            '["tag"]',
            '{"k": "v"}',
            '["path"]',
            "rollback",
            12345.0,
            0,
        )
        d = _row_to_dict(row)
        assert d["event_id"] == "id-1"
        assert d["fallback_used"] is True
        assert d["tags"] == ["tag"]
        assert d["evidence"] == {"k": "v"}
        assert d["artifact_paths"] == ["path"]

    def test_json_fallback_to_empty(self):
        row = (
            "id-2",
            "src",
            "type",
            "loop",
            "outcome",
            "backend",
            "scenario",
            "task",
            "device",
            "req",
            "entry",
            0,
            0,
            "summary",
            "not-json",
            "not-json",
            "not-json",
            "rollback",
            0.0,
            0,
        )
        d = _row_to_dict(row)
        assert d["tags"] == []
        assert d["evidence"] == []
        assert d["artifact_paths"] == []
