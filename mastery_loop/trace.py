"""Trace helpers for mastery recommendations."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecommendationTrace:
    recommendation_id: str
    evidence_refs: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "recommendation_id": self.recommendation_id,
            "evidence_refs": self.evidence_refs,
            "reasons": self.reasons,
        }
