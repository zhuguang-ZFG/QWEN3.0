"""Tests for session_memory/learning_loop/memory_channel.py — typed memory channel."""

from unittest.mock import patch

from session_memory.learning_loop.memory_channel import _feed_memory
from session_memory.learning_loop.models import TaskOutcome


class TestFeedMemory:
    def test_empty_outcome(self):
        outcome = TaskOutcome(task_id="t1", status="succeeded")
        with patch("session_memory.store.save_typed_memory") as mock:
            result = _feed_memory(outcome)
            assert "routing_lesson:success" in result["saved"]
            mock.assert_called()

    def test_passing_test_result(self):
        outcome = TaskOutcome(
            task_id="t2",
            status="succeeded",
            test_results=[{"command": "pytest", "exit_code": 0, "duration_ms": 120}],
        )
        with patch("session_memory.store.save_typed_memory") as mock:
            result = _feed_memory(outcome)
            assert "test_result:pass" in result["saved"]
            mock.assert_called()

    def test_failing_test_result(self):
        outcome = TaskOutcome(
            task_id="t3",
            status="failed",
            test_results=[{"command": "pytest", "exit_code": 1}],
        )
        with patch("session_memory.store.save_typed_memory") as mock:
            result = _feed_memory(outcome)
            assert "test_result:fail" in result["saved"]
            mock.assert_called()
