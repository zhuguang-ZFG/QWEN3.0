"""LiMa worker summary constraints.

Worker task summaries MUST include changed files, tests run, remaining
risks, and review status. The Server contract gate rejects summaries
missing these fields.

Dangerous actions (deploy, push, GitHub write, cloud, db migration,
hardware) are gated behind explicit approval metadata in tool definitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

REQUIRED_SUMMARY_FIELDS = frozenset({
    "changed_files",
    "tests_run",
    "remaining_risks",
    "review_status",
})

GATED_OUTPUT_ACTIONS = frozenset({
    "deploy", "push", "gh_pr_create", "gh_pr_merge",
    "cloud_api", "db_migration", "hardware_command",
})

VALID_REVIEW_STATUSES = frozenset({
    "pending",
    "needs_review",
    "approved",
    "rejected",
})


@dataclass
class WorkerSummary:
    changed_files: list[str] = field(default_factory=list)
    tests_run: list[str] = field(default_factory=list)
    remaining_risks: list[str] = field(default_factory=list)
    review_status: str = "pending"  # pending | needs_review | approved | rejected

    def is_complete(self) -> bool:
        return bool(
            isinstance(self.changed_files, list)
            and isinstance(self.tests_run, list)
            and isinstance(self.remaining_risks, list)
            and self.review_status in VALID_REVIEW_STATUSES
        )

    def to_dict(self) -> dict:
        return {
            "changed_files": self.changed_files,
            "tests_run": self.tests_run,
            "remaining_risks": self.remaining_risks,
            "review_status": self.review_status,
        }


def validate_worker_summary(data: dict) -> WorkerSummary | None:
    """Validate and coerce worker summary. Returns None if invalid."""
    if not isinstance(data, dict):
        return None
    missing = REQUIRED_SUMMARY_FIELDS - set(data.keys())
    if missing:
        return None
    if data.get("review_status") not in VALID_REVIEW_STATUSES:
        return None
    for field_name in ("changed_files", "tests_run", "remaining_risks"):
        if not isinstance(data.get(field_name), list):
            return None
    return WorkerSummary(
        changed_files=list(data["changed_files"]),
        tests_run=list(data["tests_run"]),
        remaining_risks=list(data["remaining_risks"]),
        review_status=str(data["review_status"]),
    )


def action_is_gated(action_name: str) -> bool:
    return action_name in GATED_OUTPUT_ACTIONS
