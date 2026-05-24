"""Evidence-weighted planning and testing recommendations."""
from __future__ import annotations

import hashlib

from .models import Recommendation, WeakPoint
from .profile_store import MasteryStore
from .trace import RecommendationTrace


def recommendations_for_files(store: MasteryStore, project: str, files: list[str]) -> list[tuple[Recommendation, RecommendationTrace]]:
    weak_points = store.list_weak_points(project)
    modules = store.list_modules(project)
    recs: list[tuple[Recommendation, RecommendationTrace]] = []
    touched = {f.replace("\\", "/") for f in files}

    for weak in weak_points:
        if _matches(weak, touched):
            recs.append(_weak_recommendation(weak))

    for module in modules:
        if any(path == module.module or path.startswith(module.module.rstrip("/") + "/") for path in touched):
            if module.review_risk >= 0.5 or module.deploy_risk >= 0.5 or module.stability_score < 0.4:
                rec = Recommendation(
                    target=module.module,
                    action="run focused regression and request extra review",
                    reason=(
                        f"stability={module.stability_score:.2f}, "
                        f"review_risk={module.review_risk:.2f}, deploy_risk={module.deploy_risk:.2f}"
                    ),
                    priority="high",
                )
                trace = RecommendationTrace(_rec_id(rec), reasons=[rec.reason])
                recs.append((rec, trace))
    return recs


def due_review_recommendations(store: MasteryStore) -> list[Recommendation]:
    return [
        Recommendation(
            target=s.target_id,
            action="run scheduled regression/review",
            reason=s.reason,
            priority="medium",
        )
        for s in store.list_schedules()
    ]


def _matches(weak: WeakPoint, touched: set[str]) -> bool:
    target = weak.target.replace("\\", "/")
    return target in touched or any(path.startswith(target.rstrip("/") + "/") for path in touched)


def _weak_recommendation(weak: WeakPoint) -> tuple[Recommendation, RecommendationTrace]:
    priority = "high" if weak.severity.lower() in {"p0", "p1", "high"} or weak.recurrence_count >= 3 else "medium"
    rec = Recommendation(
        target=weak.target,
        action="check weak point before completion",
        reason=f"{weak.kind} seen {weak.recurrence_count} time(s): {weak.description}",
        evidence_refs=[weak.last_evidence_ref] if weak.last_evidence_ref else [],
        priority=priority,
    )
    trace = RecommendationTrace(
        recommendation_id=_rec_id(rec),
        evidence_refs=rec.evidence_refs,
        reasons=[rec.reason],
    )
    return rec, trace


def _rec_id(rec: Recommendation) -> str:
    raw = f"{rec.target}|{rec.action}|{rec.reason}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
