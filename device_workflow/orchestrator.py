"""M4: Workflow orchestrator — manages per-task state and enforces transitions."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from .state import TaskState, VALID_TRANSITIONS, WorkflowTransitionError


class WorkflowOrchestrator:
    """Thread-safe per-task state machine with transition history."""

    def __init__(self) -> None:
        self._states: dict[str, TaskState] = {}
        self._history: dict[str, list[TaskState]] = {}
        self._timestamps: dict[str, list[str]] = {}
        self._lock = threading.RLock()

    def register(self, task_id: str) -> TaskState:
        """Register a new task in CREATED state."""
        with self._lock:
            self._states[task_id] = TaskState.CREATED
            self._history[task_id] = [TaskState.CREATED]
            self._timestamps[task_id] = [_now_iso()]
            return TaskState.CREATED

    def advance(self, task_id: str, target: TaskState) -> TaskState:
        """Advance task to target state. Raises WorkflowTransitionError if invalid."""
        with self._lock:
            current = self._states.get(task_id)
            if current is None:
                raise WorkflowTransitionError(f"unknown task: {task_id}")

            allowed = VALID_TRANSITIONS.get(current, frozenset())
            if target not in allowed:
                raise WorkflowTransitionError(
                    f"invalid transition: {current.value} → {target.value} "
                    f"(allowed: {', '.join(s.value for s in sorted(allowed, key=lambda s: s.value)) or 'none'})"
                )

            self._states[task_id] = target
            self._history[task_id].append(target)
            self._timestamps[task_id].append(_now_iso())
            return target

    def get_state(self, task_id: str) -> TaskState:
        """Get current state. Raises WorkflowTransitionError if unknown."""
        with self._lock:
            state = self._states.get(task_id)
            if state is None:
                raise WorkflowTransitionError(f"unknown task: {task_id}")
            return state

    def history(self, task_id: str) -> list[TaskState]:
        """Return full state transition history for a task."""
        with self._lock:
            return list(self._history.get(task_id, []))

    def snapshot(self, task_id: str) -> dict[str, Any] | None:
        """Return a serializable snapshot of task workflow state."""
        with self._lock:
            state = self._states.get(task_id)
            if state is None:
                return None
            return {
                "task_id": task_id,
                "state": state.value,
                "history": [s.value for s in self._history.get(task_id, [])],
                "timestamps": list(self._timestamps.get(task_id, [])),
            }

    def reset(self) -> None:
        """Clear all tracked state (for tests)."""
        with self._lock:
            self._states.clear()
            self._history.clear()
            self._timestamps.clear()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# Module-level singleton
workflow = WorkflowOrchestrator()
