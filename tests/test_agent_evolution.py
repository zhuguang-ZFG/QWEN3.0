"""Tests for the gated evolution loop."""

from agent_evolution.candidates import CandidateSkill, CandidateStore, extract_candidate
from agent_evolution.promote import can_activate, promote_candidate


def _make_candidate(eval_passed=False, promoted=False) -> CandidateSkill:
    return CandidateSkill(
        skill_id="abc123",
        name="skill_abc123",
        source_task_id="task_1",
        trigger_pattern="timeout",
        backend="auto",
        commands=["curl"],
        file_categories=["py"],
        created_at=1000.0,
        active=False,
        eval_passed=eval_passed,
        promoted=promoted,
    )


def test_candidate_without_eval_cannot_activate():
    c = _make_candidate(eval_passed=False, promoted=False)
    assert can_activate(c) is False


def test_candidate_with_failed_eval_cannot_activate():
    c = _make_candidate(eval_passed=False, promoted=True)
    assert can_activate(c) is False


def test_candidate_eval_passed_no_manual_flag_cannot_promote():
    store = CandidateStore()
    c = _make_candidate()
    store.add(c)
    result = promote_candidate(store, "abc123", eval_passed=True, manual_flag=False)
    assert result is False
    assert c.promoted is False


def test_candidate_eval_passed_and_manual_flag_promotes():
    store = CandidateStore()
    c = _make_candidate()
    store.add(c)
    result = promote_candidate(store, "abc123", eval_passed=True, manual_flag=True)
    assert result is True
    assert c.active is True
    assert c.promoted is True
    assert c.eval_passed is True
    assert can_activate(c) is True


def test_extract_candidate_creates_inactive():
    c = extract_candidate(
        task_id="task_99",
        failure_reason="model_unavailable",
        commands=["retry", "fallback"],
        files=["router.py", "config.yaml"],
    )
    assert c.active is False
    assert c.eval_passed is False
    assert c.promoted is False
    assert c.source_task_id == "task_99"
    assert "py" in c.file_categories
    assert "yaml" in c.file_categories
