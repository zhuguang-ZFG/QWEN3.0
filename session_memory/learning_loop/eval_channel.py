"""Eval-candidate learning channel."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from .models import TaskOutcome

_log = logging.getLogger(__name__)

_EVAL_CANDIDATES: list[dict] = []


def _feed_eval(outcome: TaskOutcome) -> dict[str, Any]:
    """Queue outcome as an eval candidate. Promotion requires evidence.

    Candidates that repeatedly succeed with the same pattern can be promoted
    by an explicit eval run. Nothing is auto-promoted.
    """
    candidate = {
        "task_id": outcome.task_id,
        "backend": outcome.backend,
        "scenario": outcome.scenario,
        "status": outcome.status,
        "test_pass_rate": _test_pass_rate(outcome.test_results),
        "changed_files_count": len(outcome.changed_files),
        "timestamp": time.time(),
    }

    _EVAL_CANDIDATES.append(candidate)
    if len(_EVAL_CANDIDATES) > 200:
        _EVAL_CANDIDATES[:] = _EVAL_CANDIDATES[-100:]

    # Only promote explicit patterns: 3+ successes with same backend+scenario
    if outcome.status in ("succeeded", "needs_review") and outcome.backend:
        _maybe_promote_pattern(outcome)

    return {"candidate_queued": True, "total_candidates": len(_EVAL_CANDIDATES)}


def _test_pass_rate(test_results: list[dict]) -> float:
    if not test_results:
        return 1.0
    passed = sum(1 for t in test_results if t.get("exit_code") == 0)
    return passed / len(test_results)


def _maybe_promote_pattern(outcome: TaskOutcome) -> None:
    """Record a pattern candidate when evidence threshold is met.

    Patterns are saved as reference_pattern memories. They do NOT
    auto-change routing. Promotion requires explicit eval gate approval
    via session_memory.eval_gate.approve_candidate().
    """
    matches = [
        c
        for c in _EVAL_CANDIDATES
        if c["backend"] == outcome.backend
        and c["scenario"] == outcome.scenario
        and c["status"] in ("succeeded", "needs_review")
        and c["task_id"] != outcome.task_id
    ]
    if len(matches) >= 3:
        try:
            from session_memory.store import save_typed_memory, query_by_type

            existing = query_by_type("reference_pattern", limit=10)
            already_recorded = any(
                f"candidate:{outcome.backend}:{outcome.scenario}" in (e.summary or "") for e in existing
            )
            if not already_recorded:
                save_typed_memory(
                    "reference_pattern",
                    f"candidate:{outcome.backend}:{outcome.scenario} — {len(matches) + 1} successes",
                    detail=json.dumps(
                        {
                            "backend": outcome.backend,
                            "scenario": outcome.scenario,
                            "evidence_count": len(matches) + 1,
                            "latest_task": outcome.task_id,
                            "recorded_at": time.time(),
                            "status": "needs_approval",
                        },
                        ensure_ascii=False,
                    ),
                )
        except ImportError as exc:
            _log.warning("session_memory.store not installed; eval candidate not saved: %s", exc)


def get_eval_candidates(limit: int = 20) -> list[dict]:
    """Return recent eval candidates (for ops/admin inspection)."""
    return _EVAL_CANDIDATES[-limit:]
