"""M4: Workflow orchestrator — manages per-task state and enforces transitions.

The orchestrator no longer keeps truth in memory. All persistent state lives in
``device_ledger.store.ledger_store``; ``WorkflowOrchestrator`` is a thin,
thread-safe projection over the append-only ledger event stream.
"""

from __future__ import annotations

import threading
from typing import Any

from device_ledger.events import new_event
from device_ledger.projection import _status_after_event, task_projection
from device_ledger.store import ledger_store

from .lock import TaskLock, ThreadTaskLock
from .state import TaskState, VALID_TRANSITIONS, WorkflowTransitionError


class WorkflowOrchestrator:
    """Thread-safe per-task state machine backed by the device ledger."""

    def __init__(self, lock_manager: TaskLock | None = None) -> None:
        # Short-lived cache keyed by task_id (event_count, TaskState) to avoid
        # replaying the ledger on every ``get_state`` call. It is not the source
        # of truth; persisted ledger events are.
        self._cache: dict[str, tuple[int, TaskState]] = {}
        self._lock = threading.RLock()
        self._lock_manager = lock_manager if lock_manager is not None else ThreadTaskLock()

    def register(
        self,
        task_id: str,
        *,
        device_id: str = "",
        task: dict[str, Any] | None = None,
    ) -> TaskState:
        """Register a new task in CREATED state by appending a ledger event."""
        if not self._lock_manager.acquire(task_id):
            raise WorkflowTransitionError(f"could not acquire lock for task {task_id}")
        try:
            with self._lock:
                resolved_device_id = device_id or (str(task.get("device_id", "")) if task else "")
                payload_task: dict[str, Any] = task if task is not None else {"task_id": task_id}
                ledger_store.append_event(
                    new_event(
                        event_type="task_created",
                        task_id=task_id,
                        device_id=resolved_device_id,
                        payload={"task": payload_task, "status": "created"},
                    )
                )
                return self._current_state(task_id)
        finally:
            self._lock_manager.release(task_id)

    def advance(self, task_id: str, target: TaskState) -> TaskState:
        """Advance task to target state. Raises WorkflowTransitionError if invalid."""
        if not self._lock_manager.acquire(task_id):
            raise WorkflowTransitionError(f"could not acquire lock for task {task_id}")
        try:
            with self._lock:
                current = self._current_state(task_id)

                allowed = VALID_TRANSITIONS.get(current, frozenset())
                if target not in allowed:
                    raise WorkflowTransitionError(
                        f"invalid transition: {current.value} \u2192 {target.value} "
                        f"(allowed: {', '.join(s.value for s in sorted(allowed, key=lambda s: s.value)) or 'none'})"
                    )

                self._append_advance_event(task_id, current, target)
                return self._current_state(task_id)
        finally:
            self._lock_manager.release(task_id)

    def get_state(self, task_id: str) -> TaskState:
        """Get current state by replaying ledger events. Raises WorkflowTransitionError if unknown."""
        with self._lock:
            return self._current_state(task_id)

    def history(self, task_id: str) -> list[TaskState]:
        """Return full workflow state transition history for a task."""
        with self._lock:
            events = self._sorted_events(task_id)
            if not events:
                raise WorkflowTransitionError(f"unknown task: {task_id}")

            states: list[TaskState] = []
            current_status = "unknown"
            for event in events:
                current_status = _status_after_event(event, current_status)
                try:
                    state = TaskState(current_status)
                except ValueError:
                    # Non-workflow states (e.g. acknowledged, paused, resumed) are
                    # recorded in the ledger but do not belong to the workflow enum.
                    continue
                if not states or states[-1] != state:
                    states.append(state)
            return states

    def snapshot(self, task_id: str) -> dict[str, Any] | None:
        """Return a serializable snapshot of task workflow state from the ledger."""
        with self._lock:
            if not self._sorted_events(task_id):
                return None
            return task_projection.rebuild_state(task_id)

    def reset(self) -> None:
        """Clear the local in-memory cache.

        Persisted ledger events are NOT deleted by this call. Tests that need a
        fully clean state should also call ``ledger_store.reset()``.
        """
        with self._lock:
            self._cache.clear()

    def _current_state(self, task_id: str) -> TaskState:
        """Rebuild current TaskState from the ledger, using the cache when fresh."""
        projection = task_projection.rebuild_state(task_id)
        event_count = projection["event_count"]
        if event_count == 0:
            raise WorkflowTransitionError(f"unknown task: {task_id}")

        cached = self._cache.get(task_id)
        if cached is not None and cached[0] == event_count:
            return cached[1]

        state = self._status_to_task_state(projection["status"], task_id)
        self._cache[task_id] = (event_count, state)
        return state

    def _status_to_task_state(self, status: str, task_id: str) -> TaskState:
        """Map a projection status string to a ``TaskState``.

        Some ledger events (``task_acknowledged``, ``task_paused``,
        ``task_resumed``) do not have a corresponding ``TaskState`` value. In
        that case we replay the event stream and return the most recent
        workflow-relevant state.
        """
        try:
            return TaskState(status)
        except ValueError:
            pass

        last_state: TaskState | None = None
        current_status = "unknown"
        for event in self._sorted_events(task_id):
            current_status = _status_after_event(event, current_status)
            try:
                last_state = TaskState(current_status)
            except ValueError:
                continue

        if last_state is None:
            raise WorkflowTransitionError(f"unknown task state: {status}")
        return last_state

    def _sorted_events(self, task_id: str) -> list[Any]:
        return sorted(ledger_store.events_for_task(task_id), key=lambda e: e.created_at or "")

    def _append_advance_event(self, task_id: str, current: TaskState, target: TaskState) -> None:
        device_id = task_projection.rebuild_state(task_id).get("device_id", "")

        if target == TaskState.DISPATCHED:
            event_type = "task_dispatched"
            payload: dict[str, Any] = {"task_id": task_id}
        elif target in {
            TaskState.PLANNED,
            TaskState.SIMULATED,
            TaskState.WAITING_APPROVAL,
            TaskState.READY_TO_DISPATCH,
            TaskState.RUNNING,
            TaskState.IN_PROGRESS,
            TaskState.RECOVERING,
        }:
            event_type = "task_updated"
            payload = {
                "state": target.value,
                "previous_state": current.value,
                "reason": f"advanced to {target.value}",
            }
        else:
            # TERMINAL, COMPLETED, FAILED, CANCELLED
            event_type = "task_terminal"
            payload = {"terminal_event": {"phase": _terminal_phase(target)}}

        ledger_store.append_event(
            new_event(
                event_type=event_type,
                task_id=task_id,
                device_id=device_id,
                payload=payload,
            )
        )


def _terminal_phase(target: TaskState) -> str:
    """Map terminal TaskState values to motion-compatible phase names."""
    return {
        TaskState.COMPLETED: "done",
        TaskState.FAILED: "failed",
        TaskState.CANCELLED: "cancelled",
    }.get(target, target.value)


# Module-level singleton
workflow = WorkflowOrchestrator()
