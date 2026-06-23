"""Tests for session_memory/eval_gate.py — promotion control."""

from session_memory.eval_gate import EvalGateConfig, EvalCandidate, eval_candidates_from_memory


class TestEvalGateConfig:
    def test_default_values(self):
        cfg = EvalGateConfig()
        assert cfg.evidence_required == 3
        assert cfg.pass_rate_threshold == 0.8
        assert cfg.require_manual_approval is True


class TestEvalCandidate:
    def test_default_values(self):
        c = EvalCandidate(pattern_key="test")
        assert c.evidence_count == 0
        assert c.pass_count == 0
        assert c.fail_count == 0
        assert c.pass_rate == 0.0

    def test_pass_rate_calculation(self):
        c = EvalCandidate(pattern_key="p", pass_count=8, fail_count=2)
        assert c.pass_rate == 0.8

    def test_zero_task_pass_rate(self):
        c = EvalCandidate(pattern_key="p")
        assert c.pass_rate == 0.0

    def test_all_tasks_passed(self):
        c = EvalCandidate(pattern_key="p", pass_count=5, fail_count=0)
        assert c.pass_rate == 1.0

    def test_meets_evidence_threshold(self):
        c = EvalCandidate(pattern_key="p", evidence_count=5)
        assert c.meets_evidence_threshold is True

    def test_below_evidence_threshold(self):
        c = EvalCandidate(pattern_key="p", evidence_count=1)
        assert c.meets_evidence_threshold is False


class TestEvalCandidatesFromMemory:
    def test_returns_list(self):
        result = eval_candidates_from_memory()
        assert isinstance(result, list)
