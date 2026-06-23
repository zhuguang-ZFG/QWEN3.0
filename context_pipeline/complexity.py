"""Request complexity assessor — compatibility facade around speculative_policy.

This module previously contained a standalone scoring implementation that
overlapped with ``speculative_policy.classify_complexity``.  It now re-exports
the unified ``score_request`` / ``classify_complexity`` logic and keeps the
legacy ``ComplexityAssessment`` dataclass for callers that need detailed
factors and topology recommendations.
"""

from dataclasses import dataclass

from speculative_policy import classify_complexity, score_request

__all__ = [
    "ComplexityAssessment",
    "assess_complexity",
    "classify_complexity",
    "dynamic_ensemble_decision",
    "score_request",
]


@dataclass
class ComplexityAssessment:
    """Result of request complexity analysis."""

    score: int  # 1-10
    factors: dict
    recommended_parallelism: int  # 1, 2, or 3
    recommended_tier: str  # "weak", "medium", "strong"


def _resolve_topology(score: int) -> tuple[int, str]:
    """Determine parallelism and tier from score."""
    if score <= 3:
        return 1, "weak"
    if score <= 6:
        return 1, "strong"
    return min(3, 1 + (score - 6)), "strong"


def assess_complexity(messages: list[dict], ide: str = "") -> ComplexityAssessment:
    """Assess request complexity to determine routing topology."""
    score, factors = score_request(messages, ide=ide)
    parallelism, tier = _resolve_topology(score)
    return ComplexityAssessment(
        score=score,
        factors=factors,
        recommended_parallelism=parallelism,
        recommended_tier=tier,
    )


def dynamic_ensemble_decision(
    messages: list[dict],
    ide: str = "",
    available_backends: list[str] | None = None,
) -> dict:
    """AgentConductor-style dynamic topology decision.

    Returns routing topology recommendation:
    - parallelism: how many backends to use
    - tier: minimum backend quality tier
    - strategy: "direct" | "single_strong" | "ensemble_race"

    ``available_backends`` is accepted for API compatibility but is not used
    by the current heuristic.
    """
    del available_backends  # reserved for future backend-aware topology
    assessment = assess_complexity(messages, ide)

    if assessment.recommended_parallelism == 1 and assessment.recommended_tier == "weak":
        strategy = "direct"
    elif assessment.recommended_parallelism == 1:
        strategy = "single_strong"
    else:
        strategy = "ensemble_race"

    return {
        "strategy": strategy,
        "parallelism": assessment.recommended_parallelism,
        "tier": assessment.recommended_tier,
        "complexity_score": assessment.score,
        "factors": assessment.factors,
    }
