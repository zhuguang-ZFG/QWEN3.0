"""Tests for session_memory/eval_gate.py — promotion control."""

from session_memory.eval_gate import EvalGateConfig, EvalCandidate, evaluate_candidate


class TestEvalGateConfig:
    def test_default_values(self):
        cfg = EvalGateConfig()
        assert cfg.evidence_required == 3
        assert cfg.pass_rate_threshold == 0.8
        assert cfg.require_manual_approval is True

    def test_custom_values(self):
        cfg = EvalGateConfig(evidence_required=5, pass_rate_threshold=0.9, require_manual_approval=False)
        assert cfg.evidence_required == 5
        assert cfg.require_manual_approval is False


class TestEvalCandidate:
    def test_default_values(self):
        c = EvalCandidate(pattern="test", domain="routing")
        assert c.task_count == 0
        assert c.pass_count == 0
        assert c.pass_rate == 0.0


class TestEvaluateCandidate:
    def test_passes_with_sufficient_evidence(self):
        result = evaluate_candidate(EvalCandidate(pattern="p", domain="d", task_count=5, pass_count=4))
        assert result["promotable"] is True

    def test_fails_with_insufficient_evidence(self):
        result = evaluate_candidate(EvalCandidate(pattern="p", domain="d", task_count=1, pass_count=1))
        assert result["promotable"] is False
        assert "insufficient_evidence" in result["reasons"]

    def test_fails_with_low_pass_rate(self):
        result = evaluate_candidate(EvalCandidate(pattern="p", domain="d", task_count=10, pass_count=3))
        assert result["promotable"] is False
        assert "pass_rate" in str(result["reasons"])

    def test_requires_manual_approval_by_default(self):
        result = evaluate_candidate(EvalCandidate(pattern="p", domain="routing", task_count=5, pass_count=5))
        assert result["requires_approval"] is True
