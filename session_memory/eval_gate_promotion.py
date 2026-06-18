"""Promotion application helpers for the eval gate."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from session_memory.store import query_by_type, save_typed_memory

if TYPE_CHECKING:
    from session_memory.eval_gate import EvalCandidate


def apply_promotion(pattern_key: str) -> dict:
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
        return {
            "applied": False,
            "error": "pattern does not meet promotion criteria",
            "evidence_count": candidate.evidence_count,
            "pass_rate": round(candidate.pass_rate, 2),
            "manual_approved": candidate.manual_approved,
        }

    # Guard: check if already promoted (idempotency)
    if _already_promoted(pattern_key):
        return {"applied": False, "error": "pattern already promoted", "pattern_key": pattern_key}

    before, after, rw_ok = _apply_routing_weights(candidate)
    if not rw_ok and candidate.backend and candidate.scenario:
        return {"applied": False, "error": "routing_weights module not available — promotion aborted"}

    _save_promotion_record(pattern_key, candidate, before, after, rw_ok)
    return {
        "applied": True,
        "pattern_key": pattern_key,
        "backend": candidate.backend,
        "scenario": candidate.scenario,
        "weight_before": before.get("weight", 1.0),
        "weight_after": after.get("weight", 1.0),
        "rw_applied": rw_ok,
    }


def _find_approved_candidate(pattern_key: str) -> "EvalCandidate | None":
    from session_memory.eval_gate import eval_candidates_from_memory

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
    except Exception:
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


def _apply_routing_weights(candidate: "EvalCandidate") -> tuple[dict, dict, bool]:
    """Apply routing weight changes for a promoted pattern. Returns (before, after, ok)."""
    if not (candidate.backend and candidate.scenario):
        return {}, {}, True  # record-only promotion
    try:
        from context_pipeline.routing_weights import get_routing_weights

        rw = get_routing_weights()
        before = rw.get_stats(candidate.backend, candidate.scenario)
        for _ in range(candidate.pass_count):
            rw.record_success(candidate.backend, candidate.scenario)
        after = rw.get_stats(candidate.backend, candidate.scenario)
        return before, after, True
    except ImportError:
        return {}, {}, False
    except Exception:
        return {}, {}, False


def _save_promotion_record(
    pattern_key: str, candidate: "EvalCandidate", before: dict, after: dict, rw_applied: bool
) -> None:
    """Persist promotion record to typed memory store."""
    save_typed_memory(
        "reference_pattern",
        f"promoted:{pattern_key}",
        detail=json.dumps(
            {
                "pattern_key": pattern_key,
                "backend": candidate.backend,
                "scenario": candidate.scenario,
                "evidence_count": candidate.pass_count + candidate.fail_count,
                "promoted_at": time.time(),
                "weight_before": before.get("weight", 1.0),
                "weight_after": after.get("weight", 1.0),
                "rw_applied": rw_applied,
                "rollback_notes": candidate.rollback_notes,
            },
            ensure_ascii=False,
        ),
    )
