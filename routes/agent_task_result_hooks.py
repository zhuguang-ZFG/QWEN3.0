"""Side effects after agent task result submission (extracted from agent_tasks)."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict

from agent_contracts.task_contract import AgentTaskResult
from routes.agent_task_schemas import TaskResultBody
from routes.agent_task_store import TaskStore

_log = logging.getLogger(__name__)


def after_task_result_submitted(
    store: TaskStore,
    task_id: str,
    body: TaskResultBody,
    result: AgentTaskResult,
) -> None:
    """Notify, learn, and record evidence — keeps route handler thin."""
    task = store.get(task_id)
    backend = body.backend or task.get("request", {}).get("backend", "")
    latency_ms = body.latency_ms or int(
        (time.time() - task.get("created_at", time.time())) * 1000
    )
    scenario = "coding"

    try:
        from observability.correlation import record_worker_task_correlation

        worker_id = (
            task.get("request", {}).get("worker_id", "")
            if isinstance(task.get("request"), dict)
            else ""
        )
        record_worker_task_correlation(
            task_id=task_id, status=result.status, worker_id=worker_id
        )
    except ImportError:
        _log.debug("observability.correlation not installed")

    if result.status == "needs_review":
        _notify_task_ready(task_id, body)

    try:
        from session_memory.learning_loop import ingest_from_agent_task_result

        ingest_from_agent_task_result(
            asdict(result),
            backend=backend,
            scenario=scenario,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        _log.warning(
            "learning_loop ingest failed task_id=%s err=%s",
            task_id,
            type(exc).__name__,
        )

    from observability.capability_evidence import record_evidence_safe

    record_evidence_safe(
        loop="lima_worker",
        request_id=task_id,
        task_id=task_id,
        entrypoint=f"/agent/tasks/{task_id}/result",
        selected_backend=backend,
        latency_ms=latency_ms,
        status=result.status,
        evidence=["agent_task_result"],
        artifact_paths=body.artifacts,
        rollback="review task result and quarantine if unsafe",
    )


def _notify_task_ready(task_id: str, body: TaskResultBody) -> None:
    try:
        from telegram_notify import notify_task_ready

        tests_passed = sum(1 for t in body.test_results if t.get("exit_code") == 0)
        tests_failed = len(body.test_results) - tests_passed
        artifact_links = {}
        for artifact in body.artifacts[:5]:
            if isinstance(artifact, str) and artifact:
                artifact_links[artifact.split("/")[-1]] = artifact

        notify_task_ready(
            task_id,
            body.summary,
            body.changed_files,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            risks=body.risks,
            artifact_links=artifact_links or None,
        )
    except Exception as exc:
        _log.warning(
            "notify_task_ready failed task_id=%s err=%s",
            task_id,
            type(exc).__name__,
        )
