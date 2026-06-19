"""Data models for the learning loop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskOutcome:
    task_id: str
    status: str  # succeeded | failed | needs_review | blocked
    goal: str = ""
    changed_files: list[str] = field(default_factory=list)
    test_results: list[dict] = field(default_factory=list)
    backend: str = ""
    scenario: str = ""
    latency_ms: int = 0
    failure_reason: str = ""
    artifacts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_action: str = ""
    worker_id: str = ""
