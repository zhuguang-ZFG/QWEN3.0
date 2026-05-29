"""Orchestrator persistence, status mapping, and event helpers."""

from __future__ import annotations

import json as _json
import logging
import os
from typing import Any

from agent_runtime.contract import (
    AgentRunResult,
    AgentRunStatus,
    redact,
    redact_value,
)
from agent_runtime.orchestrator_models import (
    AgentRunLease,
    AgentRunRequest,
    QueueStatus,
)
from agent_runtime.store import AgentRunStore

_log = logging.getLogger(__name__)


def _queue_status_for_result(result: AgentRunResult) -> QueueStatus:
    if any(step.blocked for step in result.steps):
        return QueueStatus.BLOCKED
    if result.ok:
        return QueueStatus.COMPLETED
    return QueueStatus.FAILED


def _task_status_for_queue(status: QueueStatus) -> AgentRunStatus:
    if status == QueueStatus.COMPLETED:
        return AgentRunStatus.COMPLETED
    if status == QueueStatus.FAILED:
        return AgentRunStatus.FAILED
    if status == QueueStatus.BLOCKED:
        return AgentRunStatus.WAITING_APPROVAL
    if status == QueueStatus.CANCELLED:
        return AgentRunStatus.CANCELLED
    if status == QueueStatus.RUNNING:
        return AgentRunStatus.RUNNING
    return AgentRunStatus.PENDING


def _has_terminal_or_blocked_result(store: AgentRunStore, task_id: str) -> bool:
    result = store.get_result(task_id)
    if result is None:
        return False
    if any(step.blocked for step in result.steps):
        return True
    return result.status in (AgentRunStatus.COMPLETED, AgentRunStatus.FAILED)


def _emit(event: str, data: dict[str, Any]) -> None:
    try:
        safe_data = redact_value(data)
        from agent_runtime.events import _safe_emit, _safe_stream

        _safe_emit(f"orchestrator_{event}", safe_data)
        _safe_stream(event, safe_data)
    except Exception as exc:
        _log.debug("orchestrator emit skipped: %s", type(exc).__name__)


def _state_path() -> str:
    return os.environ.get(
        "LIMA_QUEUE_STATE",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "queue_state.jsonl",
        ),
    )


def _json_dumps(obj: dict) -> str:
    return _json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _json_loads(text: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        value = _json.loads(text)
    except _json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _request_record(req: AgentRunRequest) -> dict[str, Any]:
    return {
        "_type": "queue_request",
        "request_id": redact(req.request_id),
        "task_id": redact(req.task_id),
        "goal": redact(req.goal),
        "priority": req.priority,
        "created_at": req.created_at,
        "status": req.status.value,
    }


def _lease_record(lease: AgentRunLease) -> dict[str, Any]:
    return {
        "_type": "queue_lease",
        "request_id": redact(lease.request_id),
        "worker_id": redact(lease.worker_id),
        "claimed_at": lease.claimed_at,
        "expires_at": lease.expires_at,
        "lease_sec": lease.lease_sec,
    }


def _parse_queue_status(value: object) -> QueueStatus:
    try:
        return QueueStatus(str(value))
    except ValueError:
        return QueueStatus.PENDING


from typing import Any

def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
