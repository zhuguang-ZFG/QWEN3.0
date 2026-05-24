"""Extract weak points from mastery events."""
from __future__ import annotations

from .models import MasteryEvent, WeakPoint


def weak_points_from_event(event: MasteryEvent) -> list[WeakPoint]:
    if event.outcome == "success":
        return []
    targets = event.files or event.modules or ["project"]
    kind = _kind(event)
    return [
        WeakPoint(
            project=event.project,
            kind=kind,
            target=target,
            description=event.summary,
            severity=event.severity if event.severity else "medium",
            last_evidence_ref=event.evidence_ref,
        )
        for target in targets
    ]


def _kind(event: MasteryEvent) -> str:
    if event.source == "test":
        return "test_failure"
    if event.source == "review":
        return "review_risk"
    if event.source == "route":
        return "routing_risk"
    if event.source == "deploy":
        return "deploy_risk"
    if event.source == "tool":
        return "tool_risk"
    return "mastery_risk"
