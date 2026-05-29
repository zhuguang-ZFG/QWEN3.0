"""Typed records for LiMa's TechSpar-inspired mastery loop."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MasteryEvent:
    source: str
    project: str
    outcome: str
    summary: str
    files: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    score: float = 0.0
    severity: str = "info"
    evidence_ref: str = ""
    event_id: str = ""
    created_at: str = field(default_factory=utc_now)


@dataclass
class ModuleMastery:
    project: str
    module: str
    stability_score: float = 0.5
    test_confidence: float = 0.5
    review_risk: float = 0.0
    deploy_risk: float = 0.0
    last_seen_at: str = field(default_factory=utc_now)
    next_review_at: str = ""


@dataclass
class WeakPoint:
    project: str
    kind: str
    target: str
    description: str
    severity: str = "medium"
    recurrence_count: int = 1
    last_evidence_ref: str = ""
    status: str = "open"


@dataclass
class ReviewSchedule:
    target_type: str
    target_id: str
    due_at: str
    reason: str
    interval_days: int = 1
    ease_factor: float = 2.5


@dataclass
class Recommendation:
    target: str
    action: str
    reason: str
    evidence_refs: list[str] = field(default_factory=list)
    priority: str = "medium"
