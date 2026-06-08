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
    c.mastery_evidence_refs = ["mastery://event"]
    assert can_activate(c) is False


def test_candidate_without_mastery_evidence_cannot_activate():
    c = _make_candidate(eval_passed=True, promoted=True)
    assert can_activate(c) is False


def test_candidate_eval_passed_no_manual_flag_cannot_promote():
    store = CandidateStore()
    c = _make_candidate()
    store.add(c)
    result = promote_candidate(
        store,
        "abc123",
        eval_passed=True,
        manual_flag=False,
        mastery_evidence_refs=["mastery://event"],
    )
    assert result is False
    assert c.promoted is False


def test_candidate_eval_passed_and_manual_flag_without_mastery_evidence_cannot_promote():
    store = CandidateStore()
    c = _make_candidate()
    store.add(c)
    result = promote_candidate(store, "abc123", eval_passed=True, manual_flag=True)
    assert result is False
    assert c.promoted is False


def test_candidate_eval_passed_and_manual_flag_promotes():
    store = CandidateStore()
    c = _make_candidate()
    store.add(c)
    result = promote_candidate(
        store,
        "abc123",
        eval_passed=True,
        manual_flag=True,
        mastery_evidence_refs=["mastery://event"],
    )
    assert result is True
    assert c.active is True
    assert c.promoted is True
    assert c.eval_passed is True
    assert c.mastery_evidence_refs == ["mastery://event"]
    assert can_activate(c) is True


def test_candidate_promotion_persists_mastery_evidence(tmp_path):
    persist_path = tmp_path / "candidates.json"
    store = CandidateStore(persist_path=persist_path)
    c = _make_candidate()
    store.add(c)

    result = promote_candidate(
        store,
        "abc123",
        eval_passed=True,
        manual_flag=True,
        mastery_evidence_refs=["mastery://event"],
    )

    reloaded = CandidateStore(persist_path=persist_path).get("abc123")
    assert result is True
    assert reloaded is not None
    assert reloaded.promoted is True
    assert reloaded.mastery_evidence_refs == ["mastery://event"]


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


def test_extract_candidate_from_task_evidence_records_tests_and_risks():
    from agent_evolution.candidates import extract_candidate_from_task_evidence

    candidate = extract_candidate_from_task_evidence(
        task_id="task_42",
        goal="Patch agent worker retry handling",
        result={
            "summary": "patched worker retry",
            "changed_files": ["src/lima/agent-worker-retry.ts"],
            "test_commands": ["npm.cmd test -- src/tests/agent-worker-retry.test.ts"],
            "risks": ["manual review required"],
        },
    )

    assert candidate.active is False
    assert candidate.promoted is False
    assert candidate.source_task_id == "task_42"
    assert "agent" in candidate.trigger_pattern.lower()
    assert candidate.commands == ["npm.cmd test -- src/tests/agent-worker-retry.test.ts"]
    assert "ts" in candidate.file_categories
