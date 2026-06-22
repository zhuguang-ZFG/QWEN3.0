"""Public entry points that feed task outcomes into all learning channels."""

from __future__ import annotations

import logging
from typing import Any

from .eval_channel import _feed_eval
from .memory_channel import _feed_memory
from .models import TaskOutcome
from .prompt_channel import _feed_prompt
from .routing_channel import _feed_routing

_log = logging.getLogger(__name__)


def _record_to_ledger(outcome: TaskOutcome) -> None:
    """Record a completed task outcome to the unified Outcome Ledger."""
    try:
        from session_memory.outcome_ledger import record as ledger_record

        tests_total = len(outcome.test_results)
        tests_passed = sum(1 for t in outcome.test_results if t.get("exit_code") == 0)
        outcome_str = "success" if outcome.status in ("completed", "needs_review") else "failure"
        ledger_record(
            source="agent_worker",
            event_type="task_complete",
            outcome=outcome_str,
            task_id=outcome.task_id,
            backend=outcome.backend or "",
            scenario=outcome.scenario or "coding",
            summary=f"status={outcome.status} files={len(outcome.changed_files)} tests={tests_passed}/{tests_total}",
            details={
                "status": outcome.status,
                "changed_files": outcome.changed_files[:10],
                "tests_passed": tests_passed,
                "tests_total": tests_total,
                "risks": outcome.risks[:5],
                "latency_ms": outcome.latency_ms,
            },
            tags=["agent_worker", outcome.status or "unknown"],
        )
    except Exception as exc:
        _log.warning("outcome ledger record failed: %s", exc, exc_info=True)


def _record_capability_evidence(outcome: TaskOutcome, result: dict) -> None:
    """Record capability evidence for the learning loop."""
    try:
        from observability.capability_evidence import record_evidence_safe

        record_evidence_safe(
            loop="ops_learning",
            request_id=outcome.task_id,
            task_id=outcome.task_id,
            entrypoint="session_memory.learning_loop.ingest_task_outcome",
            selected_backend=outcome.backend or "",
            latency_ms=outcome.latency_ms,
            status=outcome.status,
            evidence=[f"memory={bool(result.get('memory'))}", f"eval={bool(result.get('eval'))}"],
            rollback="promote routing/prompt changes only after eval gate",
        )
    except Exception as exc:
        _log.warning("ops_learning evidence record failed: %s", exc, exc_info=True)


def ingest_task_outcome(outcome: TaskOutcome) -> dict[str, Any]:
    """Feed a completed task outcome into all four learning channels.

    Returns a summary of what was learned (or gated).
    """
    result: dict[str, Any] = {
        "task_id": outcome.task_id,
        "memory": _feed_memory(outcome),
        "prompt": _feed_prompt(outcome),
        "routing": _feed_routing(outcome),
        "eval": _feed_eval(outcome),
    }

    _record_to_ledger(outcome)
    _record_capability_evidence(outcome, result)

    return result


def ingest_from_agent_task_result(
    result: dict[str, Any],
    *,
    backend: str = "",
    scenario: str = "",
    latency_ms: int = 0,
) -> dict[str, Any]:
    """Convenience: ingest a LiMa agent task result dict into the learning loop.

    Accepts the result format that LiMa Server receives from agent worker
    submissions (the LiMaAgentTaskResult contract).
    """
    outcome = TaskOutcome(
        task_id=str(result.get("task_id", "")),
        status=str(result.get("status", "unknown")),
        goal=str(result.get("summary", ""))[:120],
        changed_files=list(result.get("changed_files", []) or []),
        test_results=list(result.get("test_results", []) or []),
        backend=backend,
        scenario=scenario,
        latency_ms=latency_ms,
        failure_reason=str(result.get("summary", "")) if result.get("status") in ("failed", "blocked") else "",
        artifacts=list(result.get("artifacts", []) or []),
    )
    return ingest_task_outcome(outcome)
