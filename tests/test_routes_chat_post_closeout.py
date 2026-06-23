"""Tests for routes/chat_post_closeout.py helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from routes.chat_post_closeout import (
    _extract_observations,
    _quick_score,
    maybe_log_distill_queue,
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
            maybe_log_distill_queue(
                query="q", content="a", intent="chat", backend="groq"
            )
            mock_log.assert_called_once_with("q", "a", {"intent": "chat"}, "groq")

    def test_non_dict_intent_wrapped(self, monkeypatch):
        monkeypatch.setenv("DISTILL_LOG", "1")
        with patch("routes.chat_post_closeout._log_to_distill_queue") as mock_log:
            maybe_log_distill_queue(
                query="q", content="a", intent={"complexity": 0.5}, backend="x"
            )
            mock_log.assert_called_once_with(
                "q", "a", {"complexity": 0.5}, "x"
            )

    def test_exception_is_logged(self, monkeypatch, caplog):
        monkeypatch.setenv("DISTILL_LOG", "1")
        with patch(
            "routes.chat_post_closeout._log_to_distill_queue",
            side_effect=RuntimeError("boom"),
        ):
            maybe_log_distill_queue(query="q", content="a", intent={}, backend="x")
        assert "distill queue log skipped" in caplog.text
