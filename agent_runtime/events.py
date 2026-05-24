"""Agent runtime events with safe streaming and observability fallbacks."""

from __future__ import annotations

import time
import uuid
from typing import Any

from agent_runtime.contract import AgentRunResult, AgentStep, StepResult, redact, redact_value


def _safe_emit(event_type: str, data: dict[str, Any]) -> None:
    """Emit to observability.metrics if available. Never raises."""
    safe_data = redact_value(data)
    try:
        from observability.events import LiMaEvent
        from observability.metrics import record

        record(LiMaEvent(
            event_type=redact(event_type),
            timestamp=time.time(),
            metadata=safe_data,
        ))
    except Exception:
        pass


def _safe_stream(event_type: str, data: dict[str, Any]) -> str | None:
    """Emit as streaming SSE event if available. Returns SSE string or None."""
    safe_data = redact_value(data)
    try:
        from streaming_events import StreamEvent

        event = StreamEvent(event=event_type, data=safe_data)
        return event.to_sse()
    except Exception:
        return None


def emit_task_start(task_id: str, goal: str = "") -> str:
    data = {"task_id": redact(task_id), "goal": redact(goal)}
    _safe_emit("agent_task_start", data)
    sse = _safe_stream("task_start", data)
    return sse or f"data: task_start:{redact(task_id)}\n\n"


def emit_step_start(step: AgentStep) -> str:
    data = {
        "step_id": redact(step.step_id),
        "kind": step.kind.value,
        "goal": redact(step.goal),
    }
    _safe_emit("agent_step_start", data)
    sse = _safe_stream("step_start", data)
    return sse or f"data: step_start:{redact(step.step_id)}\n\n"


def emit_step_result(result: StepResult) -> str:
    data = {
        "step_id": redact(result.step_id),
        "ok": result.ok,
        "blocked": result.blocked,
        "duration_ms": result.duration_ms,
        "blocked_reason": redact(result.blocked_reason),
    }
    _safe_emit("agent_step_result", data)
    sse = _safe_stream("step_result", data)
    return sse or f"data: step_result:{redact(result.step_id)}:ok={result.ok}\n\n"


def emit_task_done(result: AgentRunResult, audit_ref: str = "") -> str:
    data = {
        "task_id": redact(result.task_id),
        "status": result.status.value,
        "audit_ref": redact(audit_ref),
    }
    _safe_emit("agent_task_done", data)
    sse = _safe_stream("done", data)
    return sse or f"data: done:{redact(result.task_id)}:{result.status.value}\n\n"


def emit_warning(message: str, task_id: str = "") -> str:
    data = {"task_id": redact(task_id), "message": redact(message)}
    _safe_emit("agent_warning", data)
    sse = _safe_stream("warning", data)
    return sse or f"data: warning:{redact(message)}\n\n"


def make_audit_ref(task_id: str) -> str:
    safe_task_id = redact(task_id)
    return f"audit-{safe_task_id}-{uuid.uuid4().hex[:8]}"
