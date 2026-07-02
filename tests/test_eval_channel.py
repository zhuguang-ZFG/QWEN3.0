"""Tests for session_memory/learning_loop/eval_channel.py — eval candidate channel."""

from session_memory.learning_loop.eval_channel import _feed_eval, _test_pass_rate, get_eval_candidates
from session_memory.learning_loop.models import TaskOutcome


class TestTestPassRate:
    def test_empty_results(self):
        assert _test_pass_rate([]) == 1.0

    def test_all_passed(self):
        results = [{"exit_code": 0}, {"exit_code": 0}]
        assert _test_pass_rate(results) == 1.0

    def test_some_failed(self):
        results = [{"exit_code": 0}, {"exit_code": 1}]
        assert _test_pass_rate(results) == 0.5


class TestFeedEval:
    def test_queues_candidate(self):
        outcome = TaskOutcome(task_id="t1", status="succeeded", backend="groq", scenario="chat")
        result = _feed_eval(outcome)
        assert result["candidate_queued"] is True

    def test_failed_status(self):
        outcome = TaskOutcome(task_id="t2", status="failed", backend="groq", scenario="chat")
        result = _feed_eval(outcome)
        assert result["candidate_queued"] is True


class TestGetEvalCandidates:
    def test_returns_list(self):
        assert isinstance(get_eval_candidates(), list)

    def test_limit(self):
        outcome = TaskOutcome(task_id="t3", status="succeeded", backend="x", scenario="y")
        _feed_eval(outcome)
        assert len(get_eval_candidates(limit=1)) <= 1
