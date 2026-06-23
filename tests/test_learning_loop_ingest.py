"""Tests for session_memory/learning_loop/ingest.py — learning loop ingestion."""

from unittest.mock import patch

from session_memory.learning_loop.ingest import ingest_task_outcome
from session_memory.learning_loop.models import TaskOutcome


class TestIngestTaskOutcome:
    def test_feeds_all_channels(self):
        outcome = TaskOutcome(task_id="t1", status="succeeded", backend="groq", scenario="chat")
        with patch("session_memory.learning_loop.ingest._feed_eval") as mock_eval, \
             patch("session_memory.learning_loop.ingest._feed_memory") as mock_memory, \
             patch("session_memory.learning_loop.ingest._feed_prompt") as mock_prompt, \
             patch("session_memory.learning_loop.ingest._feed_routing") as mock_routing:
            mock_eval.return_value = {}
            mock_memory.return_value = {}
            mock_prompt.return_value = {}
            mock_routing.return_value = {}
            result = ingest_task_outcome(outcome)
            assert "eval" in result
            assert "memory" in result
            assert "prompt" in result
            assert "routing" in result
            mock_eval.assert_called_once()
            mock_memory.assert_called_once()
            mock_prompt.assert_called_once()
            mock_routing.assert_called_once()

    def test_no_backend_routing_skipped(self):
        outcome = TaskOutcome(task_id="t2", status="succeeded", scenario="chat")
        result = ingest_task_outcome(outcome)
        assert "routing" in result
