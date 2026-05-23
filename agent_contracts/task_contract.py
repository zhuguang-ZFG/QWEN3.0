"""Task contract dataclasses for agent worker communication."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

VALID_MODES = ("plan", "patch", "test", "review")
VALID_STATUSES = (
    "accepted", "running", "succeeded", "failed", "blocked", "needs_review"
)


@dataclass
class AgentTaskRequest:
    """Inbound task specification sent to an agent worker."""

    task_id: str
    repo: str
    branch: str
    goal: str
    constraints: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    max_runtime_sec: int = 300
    mode: Literal["plan", "patch", "test", "review"] = "patch"

    def validate(self) -> None:
        """Raise ValueError if any field is invalid."""
        if self.mode not in VALID_MODES:
            raise ValueError(
                f"Invalid mode '{self.mode}'. Must be one of {VALID_MODES}"
            )
        if not self.task_id:
            raise ValueError("task_id must not be empty")
        if not self.repo:
            raise ValueError("repo must not be empty")
        if not self.branch:
            raise ValueError("branch must not be empty")
        if not self.goal:
            raise ValueError("goal must not be empty")
        if self.max_runtime_sec <= 0:
            raise ValueError("max_runtime_sec must be positive")


@dataclass
class AgentTaskResult:
    """Outbound result returned by an agent worker."""

    task_id: str
    status: Literal[
        "accepted", "running", "succeeded", "failed", "blocked", "needs_review"
    ]
    summary: str
    changed_files: list[str] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=list)
    test_results: list[dict] = field(default_factory=list)
    diff_preview: str = ""
    artifacts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_action: str = ""

    def validate(self) -> None:
        """Raise ValueError if any field is invalid."""
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{self.status}'. "
                f"Must be one of {VALID_STATUSES}"
            )
        if not self.task_id:
            raise ValueError("task_id must not be empty")
        if not self.summary:
            raise ValueError("summary must not be empty")
