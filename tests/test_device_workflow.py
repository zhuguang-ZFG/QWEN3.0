"""M4: Workflow — task state machine transitions."""

from __future__ import annotations

import pytest

from device_workflow.state import (
    TaskState,
    WorkflowTransitionError,
    VALID_TRANSITIONS,
)
from device_workflow.orchestrator import WorkflowOrchestrator


class TestTaskStates:
    """All 9 states are defined."""

    @pytest.mark.parametrize(
        "state",
        [
            "created", "planned", "simulated", "waiting_approval",
            "ready_to_dispatch", "dispatched", "running", "recovering", "terminal",
        ],
    )
    def test_state_exists(self, state: str) -> None:
        assert TaskState(state)

    def test_state_count(self) -> None:
        assert len(TaskState) == 9


class TestValidTransitions:
    """Transition table defines legal state changes."""

    def test_created_to_planned(self) -> None:
        assert TaskState.PLANNED in VALID_TRANSITIONS[TaskState.CREATED]

    def test_planned_to_simulated(self) -> None:
        assert TaskState.SIMULATED in VALID_TRANSITIONS[TaskState.PLANNED]

    def test_simulated_to_waiting_or_ready(self) -> None:
        targets = VALID_TRANSITIONS[TaskState.SIMULATED]
        assert TaskState.WAITING_APPROVAL in targets
        assert TaskState.READY_TO_DISPATCH in targets

    def test_waiting_approval_outcomes(self) -> None:
        targets = VALID_TRANSITIONS[TaskState.WAITING_APPROVAL]
        assert TaskState.READY_TO_DISPATCH in targets
        assert TaskState.TERMINAL in targets

    def test_dispatched_to_running(self) -> None:
        assert TaskState.RUNNING in VALID_TRANSITIONS[TaskState.DISPATCHED]

    def test_running_outcomes(self) -> None:
        targets = VALID_TRANSITIONS[TaskState.RUNNING]
        assert TaskState.TERMINAL in targets
        assert TaskState.RECOVERING in targets

    def test_recovering_outcomes(self) -> None:
        targets = VALID_TRANSITIONS[TaskState.RECOVERING]
        assert TaskState.RUNNING in targets
        assert TaskState.TERMINAL in targets

    def test_terminal_is_sink(self) -> None:
        assert VALID_TRANSITIONS[TaskState.TERMINAL] == frozenset()

    def test_ready_to_dispatch_to_dispatched(self) -> None:
        assert TaskState.DISPATCHED in VALID_TRANSITIONS[TaskState.READY_TO_DISPATCH]


class TestWorkflowOrchestrator:
    """Orchestrator manages task state and enforces transitions."""

    def setup_method(self) -> None:
        self.wf = WorkflowOrchestrator()

    def test_register_task(self) -> None:
        state = self.wf.register("task-001")
        assert state == TaskState.CREATED

    def test_advance_valid(self) -> None:
        self.wf.register("task-001")
        new_state = self.wf.advance("task-001", TaskState.PLANNED)
        assert new_state == TaskState.PLANNED

    def test_advance_invalid_raises(self) -> None:
        self.wf.register("task-001")
        with pytest.raises(WorkflowTransitionError):
            self.wf.advance("task-001", TaskState.RUNNING)

    def test_advance_unknown_task_raises(self) -> None:
        with pytest.raises(WorkflowTransitionError, match="unknown"):
            self.wf.advance("nonexistent", TaskState.PLANNED)

    def test_full_happy_path(self) -> None:
        self.wf.register("task-002")
        for target in (
            TaskState.PLANNED,
            TaskState.SIMULATED,
            TaskState.READY_TO_DISPATCH,
            TaskState.DISPATCHED,
            TaskState.RUNNING,
            TaskState.TERMINAL,
        ):
            self.wf.advance("task-002", target)
        assert self.wf.get_state("task-002") == TaskState.TERMINAL

    def test_approval_path(self) -> None:
        self.wf.register("task-003")
        self.wf.advance("task-003", TaskState.PLANNED)
        self.wf.advance("task-003", TaskState.SIMULATED)
        self.wf.advance("task-003", TaskState.WAITING_APPROVAL)
        self.wf.advance("task-003", TaskState.READY_TO_DISPATCH)
        assert self.wf.get_state("task-003") == TaskState.READY_TO_DISPATCH

    def test_rejection_path(self) -> None:
        self.wf.register("task-004")
        self.wf.advance("task-004", TaskState.PLANNED)
        self.wf.advance("task-004", TaskState.SIMULATED)
        self.wf.advance("task-004", TaskState.WAITING_APPROVAL)
        self.wf.advance("task-004", TaskState.TERMINAL)
        assert self.wf.get_state("task-004") == TaskState.TERMINAL

    def test_recovery_path(self) -> None:
        self.wf.register("task-005")
        for target in (
            TaskState.PLANNED, TaskState.SIMULATED,
            TaskState.READY_TO_DISPATCH, TaskState.DISPATCHED, TaskState.RUNNING,
        ):
            self.wf.advance("task-005", target)
        self.wf.advance("task-005", TaskState.RECOVERING)
        self.wf.advance("task-005", TaskState.RUNNING)
        self.wf.advance("task-005", TaskState.TERMINAL)
        assert self.wf.get_state("task-005") == TaskState.TERMINAL

    def test_history_recorded(self) -> None:
        self.wf.register("task-006")
        self.wf.advance("task-006", TaskState.PLANNED)
        self.wf.advance("task-006", TaskState.SIMULATED)
        history = self.wf.history("task-006")
        assert len(history) >= 3  # created + planned + simulated
        assert history[0] == TaskState.CREATED

    def test_multiple_tasks_independent(self) -> None:
        self.wf.register("task-A")
        self.wf.register("task-B")
        self.wf.advance("task-A", TaskState.PLANNED)
        assert self.wf.get_state("task-A") == TaskState.PLANNED
        assert self.wf.get_state("task-B") == TaskState.CREATED

    def test_reset(self) -> None:
        self.wf.register("task-007")
        self.wf.reset()
        with pytest.raises(WorkflowTransitionError, match="unknown"):
            self.wf.get_state("task-007")
