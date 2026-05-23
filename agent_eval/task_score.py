"""Task scoring and evaluation result dataclasses."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class TaskScore:
    """Multi-dimensional score for an agent task execution."""

    tests_passed: bool
    diff_minimal: bool
    security_ok: bool
    docs_updated: bool
    rollback_ready: bool
    human_review_required: bool


@dataclass
class EvalResult:
    """Full evaluation result for a completed task."""

    task_id: str
    score: TaskScore
    backend: str
    role: str
    task_mode: str
    test_command: str
    pass_fail: Literal["pass", "fail"]
    reason: str
    next_action: str


def can_auto_promote(score: TaskScore) -> bool:
    """Return True only if safe to auto-promote without human review.

    Requirements: tests passed, no security issues, no human review needed.
    """
    return (
        score.tests_passed
        and score.security_ok
        and not score.human_review_required
    )
