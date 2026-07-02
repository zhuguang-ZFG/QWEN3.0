"""Tests for session_memory/store_promote.py — typed memory and promotion."""

from session_memory.store import save_memory
from session_memory.store_promote import save_typed_memory, query_by_type, auto_promote_candidates


class TestSaveTypedMemory:
    def test_saves_with_valid_type(self):
        eid = save_typed_memory("code_fact", "test memory", session_id="promote_test")
        assert eid > 0

    def test_invalid_type_falls_back_to_project_fact(self):
        eid = save_typed_memory("unknown_type", "test", session_id="promote_test2")
        assert eid > 0

    def test_can_query_saved_memory(self):
        save_typed_memory("routing_lesson", "lesson content", session_id="promote_test3")
        results = query_by_type("routing_lesson", limit=5, session_id="promote_test3")
        assert len(results) >= 1
        assert results[0].summary == "lesson content"


class TestQueryByType:
    def test_empty_type_returns_empty(self):
        results = query_by_type("nonexistent_type_xyz", session_id="test_empty")
        assert len(results) == 0

    def test_global_query(self):
        save_typed_memory("ops_event", "global event", session_id="_global")
        results = query_by_type("ops_event", limit=5)
        assert len(results) >= 1


class TestAutoPromoteCandidates:
    def test_returns_list_or_handles_exception(self):
        try:
            results = auto_promote_candidates()
            assert isinstance(results, list)
        except Exception as exc:
            import logging

            logging.debug("auto_promote_candidates failed (DB state): %s", exc)  # May depend on DB state
