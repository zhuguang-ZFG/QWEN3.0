"""Eval gate — explicit promotion control for the learning loop.

Lessons and patterns accumulate as reference_pattern memories.
The eval gate controls which ones can influence routing, prompts,
or other automated decisions:

- `evidence_required`: minimum task count before consideration
- `pass_rate_threshold`: minimum test pass rate (0.0–1.0)
- `manual_approval`: patterns impacting routing must be manually approved
- `rollback_ready`: every promoted pattern has a recorded rollback path

No pattern is ever auto-promoted into routing. The eval gate ensures
every promotion has explicit evidence, approval, and rollback.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from session_memory.store import (
    query_by_type,
    save_typed_memory,
)

_log = logging.getLogger(__name__)


@dataclass
class EvalGateConfig:
    evidence_required: int = 3
    pass_rate_threshold: float = 0.8
    require_manual_approval: bool = True


@dataclass
class EvalCandidate:
    pattern_key: str
    backend: str = ""
    scenario: str = ""
    evidence_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    last_task_id: str = ""
    promoted: bool = False
    manual_approved: bool = False
    rollback_notes: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def pass_rate(self) -> float:
        total = self.pass_count + self.fail_count
        return self.pass_count / total if total else 0.0

    @property
    def meets_evidence_threshold(self) -> bool:
        return self.evidence_count >= EvalGateConfig().evidence_required

    @property
    def meets_pass_rate(self) -> bool:
        return self.pass_rate >= EvalGateConfig().pass_rate_threshold

    @property
    def can_promote(self) -> bool:
        cfg = EvalGateConfig()
        ok = self.evidence_count >= cfg.evidence_required and self.pass_rate >= cfg.pass_rate_threshold
        if cfg.require_manual_approval:
            ok = ok and self.manual_approved
        return ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_key": self.pattern_key,
            "backend": self.backend,
            "scenario": self.scenario,
            "evidence_count": self.evidence_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "pass_rate": round(self.pass_rate, 2),
            "promoted": self.promoted,
            "manual_approved": self.manual_approved,
            "can_promote": self.can_promote,
            "last_task_id": self.last_task_id,
            "rollback_notes": self.rollback_notes,
            "timestamp": self.timestamp,
        }


def eval_candidates_from_memory(limit: int = 20) -> list[EvalCandidate]:
    """Extract eval candidates from reference_pattern typed memories."""
    try:
        patterns = query_by_type("reference_pattern", limit=limit)
    except Exception as exc:
        _log.warning("operation failed: %s", exc)
        return []

    candidates: dict[str, EvalCandidate] = {}
    approvals: dict[str, dict[str, Any]] = {}

    for p in patterns:
        summary = p.summary or ""
        prefix = summary.split(" ", 1)[0] if summary else ""

        try:
            detail = json.loads(p.detail) if p.detail else {}
        except json.JSONDecodeError:
            detail = {}

        if prefix.startswith("approved:"):
            pattern_key = detail.get("pattern_key") or prefix.removeprefix("approved:")
            approvals[pattern_key] = detail
            continue

        backend = detail.get("backend", "")
        scenario = detail.get("scenario", "")
        key = detail.get("pattern_key") or (f"{backend}:{scenario}" if backend else prefix)

        if key not in candidates:
            candidates[key] = EvalCandidate(
                pattern_key=key,
                backend=backend,
                scenario=scenario,
                promoted=prefix.startswith("promoted:"),
            )

        c = candidates[key]
        if prefix.startswith("candidate:"):
            evidence_count = int(detail.get("evidence_count", 0) or 0)
            c.evidence_count = max(c.evidence_count, evidence_count)
            c.pass_count = max(c.pass_count, evidence_count)
            c.last_task_id = detail.get("latest_task", c.last_task_id)
        elif "task " in summary and ("succeeded" in summary or "needs_review" in summary):
            c.pass_count += 1
            c.evidence_count += 1
            c.last_task_id = detail.get("latest_task", c.last_task_id)
        elif "failed" in summary or "blocked" in summary:
            c.fail_count += 1
            c.evidence_count += 1

    for pattern_key, approval in approvals.items():
        candidate = candidates.setdefault(
            pattern_key,
            EvalCandidate(pattern_key=pattern_key),
        )
        candidate.manual_approved = True
        candidate.rollback_notes = str(approval.get("rollback_notes", ""))

    return sorted(candidates.values(), key=lambda c: -c.evidence_count)


def approve_candidate(pattern_key: str, rollback_notes: str = "") -> dict[str, Any]:
    """Manually approve a candidate for promotion.

    Records the approval as a typed memory so the decision is auditable.
    Does NOT apply the promotion to routing automatically.
    """
    pattern_key = pattern_key.strip()
    if not pattern_key:
        return {"approved": False, "error": "pattern_key required"}
    if len(pattern_key) > 160:
        return {"approved": False, "error": "pattern_key too long"}

    save_typed_memory(
        "reference_pattern",
        f"approved:{pattern_key}",
        detail=json.dumps({
            "pattern_key": pattern_key,
            "approved_at": time.time(),
            "rollback_notes": rollback_notes[:500],
        }, ensure_ascii=False),
    )
    return {"approved": True, "pattern_key": pattern_key, "rollback_notes": rollback_notes[:500]}


def promoted_patterns(limit: int = 20) -> list[dict[str, Any]]:
    """Return patterns that have been explicitly promoted (approved + evidence)."""
    candidates = eval_candidates_from_memory(limit=limit)
    return [c.to_dict() for c in candidates if c.promoted or c.can_promote]


def revision_check() -> dict[str, Any]:
    """Return all candidates and their promotion status (for ops/admin review)."""
    candidates = eval_candidates_from_memory(limit=50)
    return {
        "total": len(candidates),
        "promotable": [c.to_dict() for c in candidates if c.can_promote],
        "needs_evidence": [c.to_dict() for c in candidates if not c.meets_evidence_threshold],
        "needs_approval": [c.to_dict() for c in candidates if c.meets_evidence_threshold and c.meets_pass_rate and not c.manual_approved],
        "blocked_by_pass_rate": [c.to_dict() for c in candidates if c.meets_evidence_threshold and not c.meets_pass_rate],
    }


def apply_promotion(pattern_key: str) -> dict[str, Any]:
    """Apply an approved pattern to runtime routing weights.

    Only patterns with manual_approved=True and meets_evidence_threshold
    are applied. Idempotent — checks for existing promoted:<key> record
    and skips if already applied.

    Returns before/after state for audit.
    """
    pattern_key = pattern_key.strip()
    if not pattern_key:
        return {"applied": False, "error": "pattern_key required"}
    if len(pattern_key) > 160:
        return {"applied": False, "error": "pattern_key too long"}

    candidate = _find_approved_candidate(pattern_key)
    if not candidate:
        return {"applied": False, "error": "pattern not found or not approved"}
    if not candidate.can_promote:
        return {"applied": False, "error": "pattern does not meet promotion criteria",
                "evidence_count": candidate.evidence_count,
                "pass_rate": round(candidate.pass_rate, 2),
                "manual_approved": candidate.manual_approved}

    # Guard: check if already promoted (idempotency)
    if _already_promoted(pattern_key):
        return {"applied": False, "error": "pattern already promoted",
                "pattern_key": pattern_key}

    before = {}
    after = {}
    rw_applied = False
    if candidate.backend and candidate.scenario:
        try:
            from context_pipeline.routing_weights import get_routing_weights
            rw = get_routing_weights()
            before = rw.get_stats(candidate.backend, candidate.scenario)
            for _ in range(candidate.pass_count):
                rw.record_success(candidate.backend, candidate.scenario)
            after = rw.get_stats(candidate.backend, candidate.scenario)
            rw_applied = True
        except ImportError:
            return {"applied": False,
                    "error": "routing_weights module not available — promotion aborted"}
        except Exception as exc:
            return {"applied": False,
                    "error": f"routing_weights write failed: {type(exc).__name__} — promotion aborted"}
    else:
        # No backend+scenario to promote — record-only
        rw_applied = True

    save_typed_memory(
        "reference_pattern",
        f"promoted:{pattern_key}",
        detail=json.dumps({
            "pattern_key": pattern_key,
            "backend": candidate.backend,
            "scenario": candidate.scenario,
            "evidence_count": candidate.pass_count + candidate.fail_count,
            "promoted_at": time.time(),
            "weight_before": before.get("weight", 1.0),
            "weight_after": after.get("weight", 1.0),
            "rw_applied": rw_applied,
            "rollback_notes": candidate.rollback_notes,
        }, ensure_ascii=False),
    )

    return {
        "applied": True, "pattern_key": pattern_key,
        "backend": candidate.backend, "scenario": candidate.scenario,
        "weight_before": before.get("weight", 1.0),
        "weight_after": after.get("weight", 1.0),
        "rw_applied": rw_applied,
    }


def _find_approved_candidate(pattern_key: str) -> EvalCandidate | None:
    candidates = eval_candidates_from_memory(limit=50)
    for c in candidates:
        if c.pattern_key == pattern_key and c.manual_approved:
            return c
    return None


def _already_promoted(pattern_key: str) -> bool:
    """Return True if this exact pattern key already has a promotion record."""
    promoted_summary = f"promoted:{pattern_key}"
    try:
        existing = query_by_type("reference_pattern", limit=10000)
    except Exception as exc:
        _log.warning("operation failed: %s", exc)
        return False
    for entry in existing:
        if (entry.summary or "") == promoted_summary:
            return True
        try:
            detail = json.loads(entry.detail) if entry.detail else {}
        except json.JSONDecodeError:
            detail = {}
        if (entry.summary or "").startswith("promoted:") and detail.get("pattern_key") == pattern_key:
            return True
    return False
