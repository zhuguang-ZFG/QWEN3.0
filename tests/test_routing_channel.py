"""Tests for session_memory/learning_loop/routing_channel.py — routing feedback channel."""

from unittest.mock import MagicMock, patch

from session_memory.learning_loop.routing_channel import _feed_routing
from session_memory.learning_loop.models import TaskOutcome


class TestFeedRouting:
    def test_no_backend(self):
        outcome = TaskOutcome(task_id="t1", status="succeeded")
        result = _feed_routing(outcome)
        assert result["recorded"] is False

    def test_success(self):
        outcome = TaskOutcome(task_id="t2", status="succeeded", backend="groq", scenario="chat")
        rw = MagicMock()
        with patch("context_pipeline.routing_weights.get_routing_weights", return_value=rw):
            result = _feed_routing(outcome)
            assert result["recorded"] is True
            rw.record_success.assert_called_once()

    def test_failure(self):
        outcome = TaskOutcome(task_id="t3", status="failed", backend="groq", scenario="chat")
        rw = MagicMock()
        with patch("context_pipeline.routing_weights.get_routing_weights", return_value=rw):
            result = _feed_routing(outcome)
            assert result["recorded"] is True
            rw.record_failure.assert_called_once()
