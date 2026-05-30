"""Learning loop REST API — CLI reports task outcomes for learning.

POST /agent/learn/outcome  — Report a task outcome (success/failure)
POST /agent/learn/feedback — Report routing feedback (backend quality)
GET  /agent/learn/stats    — Get learning statistics
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from access_guard import require_private_api_key

router = APIRouter(prefix="/agent/learn", tags=["agent-learning"], dependencies=[Depends(require_private_api_key)])
_log = logging.getLogger(__name__)


class OutcomeRequest(BaseModel):
    task_id: str = Field(default="")
    backend: str = Field(...)
    scenario: str = Field(default="")
    success: bool = Field(...)
    latency_ms: float = Field(default=0.0)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    changed_files: list[str] = Field(default_factory=list)
    test_passed: bool = Field(default=True)
    summary: str = Field(default="", max_length=1000)
    telemetry: dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    backend: str = Field(...)
    scenario: str = Field(...)
    success: bool = Field(...)
    latency_ms: float = Field(default=0.0)
    quality_score: float = Field(default=0.5)


@router.post("/outcome")
async def report_outcome(req: OutcomeRequest) -> dict:
    """Report a task outcome for learning."""
    try:
        # 1. Record in request_store
        from routing_loop.request_store import get_request_store
        store = get_request_store()
        store.log_request(
            request_id=req.task_id,
            scenario=req.scenario,
            backend=req.backend,
            success=req.success,
            latency_ms=req.latency_ms,
            quality_score=req.quality_score,
        )

        # 2. Update routing weights
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        if req.success:
            rw.record_success(req.backend, req.scenario)
        else:
            rw.record_failure(req.backend, req.scenario)

        # 3. Feed learning loop
        from session_memory.learning_loop import ingest_task_outcome, TaskOutcome
        outcome = TaskOutcome(
            task_id=req.task_id or f"cli-{int(time.time())}",
            status="succeeded" if req.success else "failed",
            backend=req.backend,
            scenario=req.scenario,
            latency_ms=int(req.latency_ms),
            changed_files=req.changed_files,
        )
        ingest_task_outcome(outcome)

        telemetry_recorded = False
        if req.telemetry:
            from observability.cli_telemetry import record_cli_outcome, sanitize_cli_outcome

            telemetry_record = sanitize_cli_outcome(
                task_id=outcome.task_id,
                backend=req.backend,
                scenario=req.scenario,
                success=req.success,
                latency_ms=req.latency_ms,
                telemetry=req.telemetry,
            )
            telemetry_recorded = record_cli_outcome(telemetry_record)

        return {"ok": True, "recorded": True, "telemetry_recorded": telemetry_recorded}
    except Exception as exc:
        _log.warning("outcome report failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.post("/feedback")
async def report_feedback(req: FeedbackRequest) -> dict:
    """Report routing feedback (which backend worked well)."""
    try:
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        if req.success:
            rw.record_success(req.backend, req.scenario)
        else:
            rw.record_failure(req.backend, req.scenario)
        return {"ok": True}
    except Exception as exc:
        _log.warning("feedback report failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.get("/stats")
async def learning_stats() -> dict:
    """Get learning statistics."""
    try:
        from routing_loop.request_store import get_request_store
        from routing_ml.routing_trainer import get_training_state

        store = get_request_store()
        ts = get_training_state()

        return {
            "ok": True,
            "request_log_count": store.count(),
            "ml_training": ts,
            "routing_weights_count": _count_weights(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _count_weights() -> int:
    try:
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        return len(rw._weights) if hasattr(rw, "_weights") else 0
    except Exception:
        return 0
