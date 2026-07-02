"""Tests for routes/chat_post_closeout.py helpers."""

from __future__ import annotations

from unittest.mock import patch


from routes.chat_post_closeout import (
    _extract_observations,
    _log_to_distill_queue,
    _quick_score,
    maybe_log_distill_queue,
    persist_session_memory,
    record_capability_evidence,
    record_chat_observability,
)


class TestQuickScore:
    def test_empty_answer_is_zero(self):
        assert _quick_score("query", "") == 0.0

    def test_short_answer_is_compliance_only(self):
        # length < 50 yields zero length score, but non-empty answer still
        # contributes the compliance and overlap components.
        assert _quick_score("query", "short") == 0.25

    def test_ideal_length_and_overlap(self):
        query = "explain python decorators"
        answer = "Explain Python decorators with examples and steps. " * 5
        score = _quick_score(query, answer)
        assert 0.7 <= score <= 1.0

    def test_apology_reduces_compliance(self):
        query = "how to fix this"
        answer = "抱歉，我无法回答这个问题" * 20  # length >= 100
        score = _quick_score(query, answer)
        # compliance drops from 1.0 to 0.3
        assert score < 0.5

    def test_code_block_and_list_boost_format(self):
        answer = "```python\nx = 1\n```\n1. first\n2. second"
        score = _quick_score("code", answer)
        assert score > 0.4

    def test_very_long_answer_penalty_capped(self):
        answer = "word " * 2000
        score = _quick_score("word", answer)
        assert score >= 0.3


class TestExtractObservations:
    def test_area_tags(self):
        obs = _extract_observations("fix router", "")
        assert any(tag == "observation" and "area:routing" in val for tag, val in obs)

    def test_success_outcome(self):
        obs = _extract_observations("test", "it works now")
        assert any(tag == "outcome" and "success:" in val for tag, val in obs)

    def test_issue_outcome(self):
        obs = _extract_observations("test", "it failed with error")
        assert any(tag == "outcome" and "issue:" in val for tag, val in obs)

    def test_file_mention(self):
        obs = _extract_observations("see server.py", "")
        assert any(tag == "file_mention" and "server.py" in val for tag, val in obs)

    def test_error_seen(self):
        obs = _extract_observations("got TypeError", "")
        assert any(tag == "error_seen" and "TypeError" in val for tag, val in obs)

    def test_capped_at_eight(self):
        obs = _extract_observations("router test server.py deploy.py cli.py proxy.py", "error bug fail")
        assert len(obs) <= 8


class TestMaybeLogDistillQueue:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.setenv("DISTILL_LOG", "0")
        with patch("routes.chat_post_closeout._log_to_distill_queue") as mock_log:
            maybe_log_distill_queue(query="q", content="a", intent={}, backend="x")
            mock_log.assert_not_called()

    def test_enabled_calls_log(self, monkeypatch):
        monkeypatch.setenv("DISTILL_LOG", "1")
        with patch("routes.chat_post_closeout._log_to_distill_queue") as mock_log:
            maybe_log_distill_queue(query="q", content="a", intent="chat", backend="groq")
            mock_log.assert_called_once_with("q", "a", {"intent": "chat"}, "groq")

    def test_non_dict_intent_wrapped(self, monkeypatch):
        monkeypatch.setenv("DISTILL_LOG", "1")
        with patch("routes.chat_post_closeout._log_to_distill_queue") as mock_log:
            maybe_log_distill_queue(query="q", content="a", intent={"complexity": 0.5}, backend="x")
            mock_log.assert_called_once_with("q", "a", {"complexity": 0.5}, "x")

    def test_exception_is_logged(self, monkeypatch, caplog):
        monkeypatch.setenv("DISTILL_LOG", "1")
        with patch(
            "routes.chat_post_closeout._log_to_distill_queue",
            side_effect=RuntimeError("boom"),
        ):
            maybe_log_distill_queue(query="q", content="a", intent={}, backend="x")
        assert "distill queue log skipped" in caplog.text


class TestLogToDistillQueue:
    def test_disabled_does_nothing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DISTILL_LOG", "0")
        monkeypatch.setattr("routes.chat_post_closeout._DISTILL_QUEUE_DIR", str(tmp_path))
        _log_to_distill_queue("q", "answer", {"intent": "chat"}, "groq")
        assert not list(tmp_path.iterdir())

    def test_local_backend_skipped(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DISTILL_LOG", "1")
        monkeypatch.setattr("routes.chat_post_closeout._DISTILL_QUEUE_DIR", str(tmp_path))
        _log_to_distill_queue("q", "answer", {"intent": "chat"}, "local")
        assert not list(tmp_path.iterdir())

    def test_empty_or_unavailable_answer_skipped(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DISTILL_LOG", "1")
        monkeypatch.setattr("routes.chat_post_closeout._DISTILL_QUEUE_DIR", str(tmp_path))
        _log_to_distill_queue("q", "", {"intent": "chat"}, "groq")
        _log_to_distill_queue("q", "后端暂时不可用", {"intent": "chat"}, "groq")
        assert not list(tmp_path.iterdir())

    def test_writes_entry_when_enabled(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DISTILL_LOG", "1")
        monkeypatch.setattr("routes.chat_post_closeout._DISTILL_QUEUE_DIR", str(tmp_path))
        _log_to_distill_queue("what is python", "Python is a language.", {"intent": "chat"}, "groq")
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        import json

        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["query"] == "what is python"
        assert data["source_backend"] == "groq"
        assert "quality_score" in data


class TestPersistSessionMemory:
    def test_saves_user_and_assistant_messages(self, monkeypatch):
        saved = []

        def fake_save(sid, role, content):
            saved.append((sid, role, content))

        monkeypatch.setattr("session_memory.store.save_memory", fake_save)
        monkeypatch.setattr("session_memory.store.save_typed_memory", lambda *args, **kw: None)
        monkeypatch.setattr("session_memory.compactor.needs_compaction", lambda _sid: False)
        persist_session_memory(
            client_ip="1.2.3.4",
            memory_session_id="sid-1",
            query="hello",
            content="hi there",
        )
        assert ("sid-1", "user", "hello") in saved
        assert ("sid-1", "assistant", "hi there") in saved

    def test_fallback_to_raw_when_typed_fails(self, monkeypatch):
        saved = []

        def fake_save(sid, role, content):
            saved.append((role, content))

        def fake_typed_save(*args, **kw):
            raise RuntimeError("boom")

        monkeypatch.setattr("session_memory.store.save_memory", fake_save)
        monkeypatch.setattr("session_memory.store.save_typed_memory", fake_typed_save)
        monkeypatch.setattr("session_memory.compactor.needs_compaction", lambda _sid: False)
        persist_session_memory(
            client_ip="1.2.3.4",
            memory_session_id=None,
            query="fix router",
            content="done",
        )
        assert any(role == "observation" for role, _ in saved)


class TestRecordChatObservability:
    def test_records_correlation(self, monkeypatch):
        called = {}

        def fake_record(**kwargs):
            called.update(kwargs)

        monkeypatch.setattr("observability.correlation.record_request_correlation", fake_record)
        record_chat_observability(chat_id="cid", backend="groq", duration_ms=123)
        assert called["request_id"] == "cid"
        assert called["backend"] == "groq"
        assert called["latency_ms"] == 123


class TestRecordCapabilityEvidence:
    def test_records_evidence(self, monkeypatch):
        called = {}

        def fake_record(**kwargs):
            called.update(kwargs)

        monkeypatch.setattr("observability.capability_evidence.record_evidence", fake_record)
        record_capability_evidence(request_id="rid", backend="groq", fallback_used=True, latency_ms=50)
        assert called["loop"] == "chat_ide"
        assert called["selected_backend"] == "groq"
        assert called["fallback_used"] is True
