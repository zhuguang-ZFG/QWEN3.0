"""Routing-feedback learning channel."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from .models import TaskOutcome

_log = logging.getLogger(__name__)


def _feed_routing(outcome: TaskOutcome) -> dict[str, Any]:
    """Record routing decision outcome for future route quality analysis.

    Does NOT change routing weights — only records evidence.
    Route weight changes require explicit eval gate.
    """
    if not outcome.backend:
        return {"recorded": False, "reason": "no backend recorded"}

    feedback: dict[str, Any] = {
        "task_id": outcome.task_id,
        "backend": outcome.backend,
        "scenario": outcome.scenario,
        "status": outcome.status,
        "latency_ms": outcome.latency_ms,
        "timestamp": time.time(),
    }

    try:
        from context_pipeline.routing_weights import get_routing_weights

        rw = get_routing_weights()
        if outcome.status in ("succeeded", "needs_review"):
            rw.record_success(outcome.backend, outcome.scenario)
        else:
            rw.record_failure(outcome.backend, outcome.scenario)
    except ImportError as exc:
        _log.warning("context_pipeline.routing_weights not installed; routing feedback not recorded: %s", exc)

    try:
        from session_memory.store import save_typed_memory

        save_typed_memory(
            "routing_lesson",
            f"route:{outcome.backend} scenario={outcome.scenario} status={outcome.status}",
            detail=json.dumps(feedback, ensure_ascii=False),
        )
    except ImportError as exc:
        _log.warning("session_memory.store not installed; routing lesson not saved: %s", exc)

    return {"recorded": True, "backend": outcome.backend, "scenario": outcome.scenario}
