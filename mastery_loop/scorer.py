"""Scoring rules for mastery events and module profiles."""
from __future__ import annotations

from .models import MasteryEvent, ModuleMastery, utc_now


def apply_event_to_module(current: ModuleMastery | None, event: MasteryEvent, module: str) -> ModuleMastery:
    if current:
        mastery = ModuleMastery(
            project=current.project,
            module=current.module,
            stability_score=current.stability_score,
            test_confidence=current.test_confidence,
            review_risk=current.review_risk,
            deploy_risk=current.deploy_risk,
            last_seen_at=current.last_seen_at,
            next_review_at=current.next_review_at,
        )
    else:
        mastery = ModuleMastery(project=event.project, module=module)
    delta = _bounded_delta(event.score)
    mastery.stability_score = _clamp(mastery.stability_score + delta)
    if event.source == "test":
        mastery.test_confidence = _clamp(mastery.test_confidence + (0.08 if event.outcome == "success" else -0.12))
    if event.source == "review":
        mastery.review_risk = _clamp(mastery.review_risk + (0.15 if event.outcome != "success" else -0.05))
    if event.source == "deploy":
        mastery.deploy_risk = _clamp(mastery.deploy_risk + (0.2 if event.outcome != "success" else -0.08))
    mastery.last_seen_at = utc_now()
    return mastery


def score_event(event: MasteryEvent) -> float:
    if event.score:
        return event.score
    if event.outcome == "success":
        return 0.5
    if event.outcome == "blocked":
        return -0.3
    if event.outcome == "flaky":
        return -0.4
    return -0.6


def _bounded_delta(score: float) -> float:
    return max(-0.2, min(0.15, score / 5.0))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))
