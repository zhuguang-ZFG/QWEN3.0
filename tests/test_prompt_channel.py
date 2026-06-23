"""Tests for session_memory/learning_loop/prompt_channel.py — prompt profile channel."""

from session_memory.learning_loop.prompt_channel import _feed_prompt, get_prompt_profile_stats
from session_memory.learning_loop.models import TaskOutcome


class TestFeedPrompt:
    def test_empty_outcome(self):
        outcome = TaskOutcome(task_id="t1", status="succeeded", scenario="chat", goal="")
        result = _feed_prompt(outcome)
        assert result["profile_key"] == "chat:"
        assert result["status"] == "succeeded"

    def test_records_profile_key(self):
        outcome = TaskOutcome(task_id="t2", status="succeeded", scenario="coding", goal="refactor")
        result = _feed_prompt(outcome)
        stats = get_prompt_profile_stats()
        assert "coding:refactor" in stats
        assert stats["coding:refactor"]["total"] >= 1

    def test_counts_tests(self):
        outcome = TaskOutcome(
            task_id="t3",
            status="succeeded",
            scenario="test",
            goal="run",
            test_results=[{"exit_code": 0}, {"exit_code": 1}],
        )
        _feed_prompt(outcome)
        stats = get_prompt_profile_stats()
        assert "test:run" in stats
        assert stats["test:run"]["total"] >= 1
