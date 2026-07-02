"""Tests for typed memory and memory daemon."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _typed_memory_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_SESSION_DB", str(tmp_path / "typed.db"))


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
        assert "device_draw_failed" in MEMORY_TYPES
        assert "device_draw_turn" in MEMORY_TYPES
        assert len(MEMORY_TYPES) == 12


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

        data = json.dumps(
            [
                {"type": "routing_lesson", "summary": "scnet is fast"},
                {"type": "code_fact", "summary": "route() has 5 layers"},
            ]
        )
        facts = _extract_facts("data.json", data)
        assert len(facts) == 2
        assert facts[0] == ("routing_lesson", "scnet is fast")

    def test_classify_line(self):
        from session_memory.daemon import _classify_line

        assert _classify_line("deployed to VPS") == "ops_event"
        assert _classify_line("test passed 34/34") == "test_result"
        assert _classify_line("backend fallback chain") == "routing_lesson"
        assert _classify_line("auth token leaked") == "security_lesson"

    def test_ingest_inbox_empty_dir(self, monkeypatch, tmp_path):
        from session_memory.daemon import _ingest_inbox

        monkeypatch.setenv("LIMA_MEMORY_INBOX", str(tmp_path))
        assert _ingest_inbox() == 0

    def test_run_once_ingests_env_inbox_and_archives_file(self, monkeypatch, tmp_path):
        from session_memory.daemon import run_once
        from session_memory.store import query_by_type

        monkeypatch.setenv("LIMA_MEMORY_INBOX", str(tmp_path))
        note = tmp_path / "ops.md"
        note.write_text("- deployed memory daemon outside request path\n", encoding="utf-8")

        result = run_once(consolidate=False)

        assert result["ingested"] == 1
        assert result["consolidated"] == 0
        assert (tmp_path / ".processed" / "ops.md").exists()
        memories = query_by_type("ops_event")
        assert any("memory daemon" in entry.summary for entry in memories)

    def test_run_once_consolidates_without_request_path(self):
        from session_memory.daemon import run_once
        from session_memory.store import count_memories, save_memory

        session_id = "daemon-consolidate"
        for i in range(25):
            save_memory(session_id, "exchange", f"daemon memory {i}")

        before = count_memories(session_id)
        result = run_once(ingest=False, consolidate=True)
        after = count_memories(session_id)

        assert result["consolidated"] >= 1
        assert after < before

    def test_daemon_status_uses_current_env_config(self, monkeypatch, tmp_path):
        from session_memory.daemon import daemon_status

        monkeypatch.setenv("LIMA_MEMORY_INBOX", str(tmp_path))
        monkeypatch.setenv("LIMA_MEMORY_CONSOLIDATION_INTERVAL", "7")

        status = daemon_status()

        assert status["inbox_dir"] == str(tmp_path)
        assert status["interval_seconds"] == 7
        assert "running" in status

    @pytest.mark.asyncio
    async def test_start_daemon_is_idempotent_and_stop_cancels_task(self, monkeypatch):
        import asyncio
        import session_memory.daemon as daemon

        await daemon.stop_daemon()

        async def fake_loop():
            while daemon.daemon_status()["running"]:
                await asyncio.sleep(0.01)

        monkeypatch.setattr(daemon, "_daemon_loop", fake_loop)

        first = await daemon.start_daemon()
        second = await daemon.start_daemon()
        running = daemon.daemon_status()
        await daemon.stop_daemon()
        stopped = daemon.daemon_status()

        assert first["started"] is True
        assert second["started"] is False
        assert running["running"] is True
        assert running["task_alive"] is True
        assert stopped["running"] is False
        assert stopped["task_alive"] is False


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

        save_typed_memory("invented_type", "some fact")
        results = query_by_type("project_fact")
        assert len(results) >= 1
        assert "some fact" in results[0].summary

    def test_unknown_type_records_original_in_detail(self):
        from session_memory.store import save_typed_memory, _get_conn

        save_typed_memory("weird_category", "test detail recording")
        conn = _get_conn()
        row = conn.execute("SELECT detail FROM memories WHERE summary='test detail recording'").fetchone()
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
        assert len(facts) == 1
        assert "[REDACTED]" in facts[0][1]
        assert "sk-abc12345" not in facts[0][1]

    def test_redacts_bearer_token(self):
        from session_memory.daemon import _extract_facts

        facts = _extract_facts("notes.md", "- token = Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert len(facts) == 1
        assert "[REDACTED]" in facts[0][1]
        assert "Bearer eyJ" not in facts[0][1]

    def test_passes_normal_text(self):
        from session_memory.daemon import _extract_facts

        facts = _extract_facts("notes.md", "- deployed v3 to server successfully")
        assert len(facts) == 1

    def test_save_memory_never_falls_back_to_raw_private_key(self):
        from session_memory.store import get_recent_memories, save_memory

        private_key = "-----BEGIN OPENSSH PRIVATE KEY-----\nsecret-body"
        save_memory("redact-session", "user", private_key, detail=private_key)

        memory = get_recent_memories("redact-session", limit=1)[0]
        assert "OPENSSH PRIVATE KEY" not in memory.summary
        assert "OPENSSH PRIVATE KEY" not in memory.detail
        assert memory.summary == "[REDACTED]"
        assert memory.detail == "[REDACTED]"

    def test_promote_memory_redacts_evidence_before_storage(self):
        from session_memory.store import get_recent_memories, promote_memory, save_memory

        memory_id = save_memory("promote-redact", "user", "keep this routing lesson")
        # Promotion with secret-bearing evidence is rejected
        assert not promote_memory(
            memory_id,
            "routing_lesson",
            evidence="token = Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        )
        # Promotion with clean evidence succeeds
        assert promote_memory(
            memory_id,
            "routing_lesson",
            evidence="user confirmed this routing pattern is reusable",
        )

        memory = get_recent_memories("promote-redact", limit=1)[0]
        assert "Bearer eyJ" not in memory.detail
        assert memory.memory_type == "routing_lesson"
        assert "user confirmed" in memory.detail
