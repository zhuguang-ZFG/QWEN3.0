"""Tests for typed memory and memory daemon."""
import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("LIMA_SESSION_DB", os.path.join(tempfile.gettempdir(), "lima_test_typed.db"))


class TestTypedMemory:
    def setup_method(self):
        from session_memory.store import _get_conn
        conn = _get_conn()
        conn.execute("DELETE FROM memories")
        conn.commit()
        conn.close()

    def test_save_and_query_typed_memory(self):
        from session_memory.store import save_typed_memory, query_by_type
        save_typed_memory("routing_lesson", "scnet_ds_flash is fastest")
        save_typed_memory("ops_event", "deployed v3 to VPS")
        save_typed_memory("routing_lesson", "groq has 429 rate limits")

        results = query_by_type("routing_lesson")
        assert len(results) == 2
        assert "groq" in results[0].summary

    def test_query_by_type_with_session_scope(self):
        from session_memory.store import save_typed_memory, query_by_type
        save_typed_memory("code_fact", "route() has 5 layers", session_id="sess1")
        save_typed_memory("code_fact", "http_caller uses urllib", session_id="sess2")

        results = query_by_type("code_fact", session_id="sess1")
        assert len(results) == 1
        assert "5 layers" in results[0].summary

    def test_memory_types_constant(self):
        from session_memory.store import MEMORY_TYPES
        assert "routing_lesson" in MEMORY_TYPES
        assert "user_pref" in MEMORY_TYPES
        assert len(MEMORY_TYPES) == 10


class TestMemoryDaemon:
    def test_extract_facts_from_markdown(self):
        from session_memory.daemon import _extract_facts
        facts = _extract_facts("notes.md", "- deployed v3 to server\n- test passed 100%\n- route fallback improved")
        assert len(facts) == 3
        types = [t for t, _ in facts]
        assert "ops_event" in types
        assert "test_result" in types

    def test_extract_facts_from_json(self):
        from session_memory.daemon import _extract_facts
        import json
        data = json.dumps([
            {"type": "routing_lesson", "summary": "scnet is fast"},
            {"type": "code_fact", "summary": "route() has 5 layers"},
        ])
        facts = _extract_facts("data.json", data)
        assert len(facts) == 2
        assert facts[0] == ("routing_lesson", "scnet is fast")

    def test_classify_line(self):
        from session_memory.daemon import _classify_line
        assert _classify_line("deployed to VPS") == "ops_event"
        assert _classify_line("test passed 34/34") == "test_result"
        assert _classify_line("backend fallback chain") == "routing_lesson"
        assert _classify_line("auth token leaked") == "security_lesson"

    def test_ingest_inbox_empty_dir(self):
        from session_memory.daemon import _ingest_inbox
        import tempfile
        os.environ["LIMA_MEMORY_INBOX"] = tempfile.mkdtemp()
        assert _ingest_inbox() == 0
