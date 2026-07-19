"""M4: Workflow state machine — task lifecycle states and valid transitions."""

from __future__ import annotations

from enum import Enum


class TaskState(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    SIMULATED = "simulated"
    WAITING_APPROVAL = "waiting_approval"
    READY_TO_DISPATCH = "ready_to_dispatch"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    IN_PROGRESS = "in_progress"
    RECOVERING = "recovering"
    TERMINAL = "terminal"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowEvent(str, Enum):
    PLAN_READY = "plan_ready"
    SIM_READY = "sim_ready"
    REQUIRES_APPROVAL = "requires_approval"
    AUTO_APPROVE = "auto_approve"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISPATCH = "dispatch"
    START = "start"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"
    ERROR = "error"
    RECOVERED = "recovered"


class WorkflowTransitionError(ValueError):
    """Raised when a state transition is invalid."""


# Valid transitions: source → frozenset of allowed targets
VALID_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.CREATED: frozenset({TaskState.PLANNED}),
    TaskState.PLANNED: frozenset({TaskState.SIMULATED}),
    TaskState.SIMULATED: frozenset({TaskState.WAITING_APPROVAL, TaskState.READY_TO_DISPATCH}),
    TaskState.WAITING_APPROVAL: frozenset({TaskState.READY_TO_DISPATCH, TaskState.TERMINAL}),
    TaskState.READY_TO_DISPATCH: frozenset({TaskState.DISPATCHED}),
    TaskState.DISPATCHED: frozenset({TaskState.RUNNING, TaskState.IN_PROGRESS, TaskState.FAILED, TaskState.CANCELLED}),
    TaskState.RUNNING: frozenset({TaskState.TERMINAL, TaskState.RECOVERING}),
    TaskState.IN_PROGRESS: frozenset(
        {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED, TaskState.RECOVERING}
    ),
    TaskState.RECOVERING: frozenset({TaskState.RUNNING, TaskState.TERMINAL, TaskState.IN_PROGRESS}),
    TaskState.TERMINAL: frozenset(),
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset({TaskState.RECOVERING, TaskState.TERMINAL}),
    TaskState.CANCELLED: frozenset(),
}

# Mapping from workflow TaskState to the set of task_store.status values that are
# considered consistent. Used during startup recovery to flag divergence without
# auto-correcting the execution-side view.
STATE_TO_STORE_STATUS: dict[TaskState, frozenset[str]] = {
    TaskState.CREATED: frozenset({"created"}),
    TaskState.PLANNED: frozenset({"created", "queued"}),
    TaskState.SIMULATED: frozenset({"created", "queued"}),
    TaskState.WAITING_APPROVAL: frozenset({"created", "queued", "pending"}),
    TaskState.READY_TO_DISPATCH: frozenset({"created", "queued", "pending"}),
    TaskState.DISPATCHED: frozenset({"dispatching", "dispatched"}),
    TaskState.RUNNING: frozenset({"running"}),
    TaskState.IN_PROGRESS: frozenset({"running", "processing", "progress"}),
    TaskState.RECOVERING: frozenset({"running", "processing"}),
    TaskState.TERMINAL: frozenset({"completed"}),
    TaskState.COMPLETED: frozenset({"completed"}),
    TaskState.FAILED: frozenset({"failed"}),
    TaskState.CANCELLED: frozenset({"cancelled"}),
}
