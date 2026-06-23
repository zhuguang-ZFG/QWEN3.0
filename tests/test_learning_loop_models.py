"""Tests for session_memory/learning_loop/models.py — learning loop models."""

from session_memory.learning_loop.models import TaskOutcome


class TestTaskOutcome:
    def test_default_values(self):
        outcome = TaskOutcome(task_id="t1", status="succeeded")
        assert outcome.task_id == "t1"
        assert outcome.status == "succeeded"
        assert outcome.goal == ""
        assert outcome.changed_files == []
        assert outcome.test_results == []
        assert outcome.backend == ""

    def test_custom_values(self):
        outcome = TaskOutcome(
            task_id="t2",
            status="failed",
            goal="fix bug",
            changed_files=["a.py"],
            test_results=[{"name": "test_x", "passed": False}],
            backend="groq",
            failure_reason="timeout",
        )
        assert outcome.goal == "fix bug"
        assert outcome.changed_files == ["a.py"]
        assert outcome.failure_reason == "timeout"
