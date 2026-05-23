"""Gated promotion logic for candidate skills."""

from agent_evolution.candidates import CandidateSkill, CandidateStore


def can_activate(candidate: CandidateSkill) -> bool:
    """A candidate can activate only after eval and manual promotion."""
    return candidate.eval_passed and candidate.promoted


def promote_candidate(
    store: CandidateStore,
    skill_id: str,
    eval_passed: bool,
    manual_flag: bool,
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
    candidate.eval_passed = True
    candidate.active = True
    candidate.promoted = True
    return True
