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


class TestTypedMemoryValidation:
    """Phase 0 Step 8: Unknown memory_type normalization."""

    def setup_method(self):
        from session_memory.store import _get_conn
        conn = _get_conn()
        conn.execute("DELETE FROM memories")
        conn.commit()
        conn.close()

    def test_unknown_type_normalized_to_project_fact(self):
        from session_memory.store import save_typed_memory, query_by_type
        entry_id = save_typed_memory("invented_type", "some fact")
        results = query_by_type("project_fact")
        assert len(results) >= 1
        assert "some fact" in results[0].summary

    def test_unknown_type_records_original_in_detail(self):
        from session_memory.store import save_typed_memory, _get_conn
        save_typed_memory("weird_category", "test detail recording")
        conn = _get_conn()
        row = conn.execute(
            "SELECT detail FROM memories WHERE summary='test detail recording'"
        ).fetchone()
        conn.close()
        assert "original_type=weird_category" in row[0]

    def test_known_type_passes_through(self):
        from session_memory.store import save_typed_memory, query_by_type
        save_typed_memory("routing_lesson", "known type works")
        results = query_by_type("routing_lesson")
        assert any("known type works" in r.summary for r in results)


class TestMemoryDaemonRedaction:
    """Phase 0 Step 7: Secret redaction in daemon."""

    def test_redacts_sk_key(self):
        from session_memory.daemon import _extract_facts
        facts = _extract_facts("notes.md", "- api key is sk-abc123456789012345678901234567890")
        assert len(facts) == 0

    def test_redacts_bearer_token(self):
        from session_memory.daemon import _extract_facts
        facts = _extract_facts("notes.md", "- token = Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert len(facts) == 0

    def test_passes_normal_text(self):
        from session_memory.daemon import _extract_facts
        facts = _extract_facts("notes.md", "- deployed v3 to server successfully")
        assert len(facts) == 1
