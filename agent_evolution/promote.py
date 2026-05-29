"""Gated promotion logic for candidate skills."""

from agent_evolution.candidates import CandidateSkill, CandidateStore


def can_activate(candidate: CandidateSkill) -> bool:
    """A candidate can activate only after eval and manual promotion."""
    return candidate.eval_passed and candidate.promoted and bool(candidate.mastery_evidence_refs)


def promote_candidate(
    store: CandidateStore,
    skill_id: str,
    eval_passed: bool,
    manual_flag: bool,
    mastery_evidence_refs: list[str] | None = None,
) -> bool:
    """Promote a candidate through the gate.

    Both eval_passed and manual_flag must be True.
    Returns True on successful promotion, False otherwise.
    """
    candidate = store.get(skill_id)
    if candidate is None:
        return False
    if not eval_passed:
        return False
    if not manual_flag:
        return False
    evidence_refs = [ref for ref in (mastery_evidence_refs or []) if ref]
    if not evidence_refs:
        return False
    candidate.eval_passed = True
    candidate.mastery_evidence_refs = evidence_refs
    candidate.active = True
    candidate.promoted = True
    store.update(candidate)
    return True
