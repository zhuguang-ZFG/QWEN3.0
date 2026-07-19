"""C1 Phase 3: workflow startup recovery and consistency checks."""

from __future__ import annotations

import logging
import re
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import device_gateway.store as _gateway_store
from device_gateway.memory_store import InMemoryDeviceTaskStore
from device_gateway.store import set_task_store_for_tests, task_store
from device_ledger.store import InMemoryLedgerStore, ledger_store, ledger_manager, set_ledger_store_for_tests
from device_workflow.orchestrator import WorkflowOrchestrator, workflow
from device_workflow.startup_recovery import recover_inflight_tasks
from device_workflow.state import TaskState


def _wait_for_recovery_log(caplog: pytest.LogCaptureFixture, *, timeout: float = 2.5) -> None:
    """Wait for the lifespan recovery task to log completion."""
    for _ in range(int(timeout / 0.05)):
        if "workflow startup recovery completed" in caplog.text:
            return
        time.sleep(0.05)
    raise TimeoutError(f"workflow startup recovery completed not seen within {timeout}s; caplog={caplog.text!r}")


def _prepare_inflight_stores(task_id: str):
    """Create fresh stores, populate one queued task, and return a restore callable."""
    original_task_store = _gateway_store.task_store
    original_ledger_store = ledger_manager.store

    fresh_task_store = InMemoryDeviceTaskStore()
    set_task_store_for_tests(fresh_task_store)
    fresh_ledger_store = InMemoryLedgerStore()
    set_ledger_store_for_tests(fresh_ledger_store)

    fresh_task_store.create_task_state({"task_id": task_id, "device_id": "dev-1"}, status="queued")
    workflow = WorkflowOrchestrator()
    workflow.register(task_id, device_id="dev-1", task={"task_id": task_id, "device_id": "dev-1"})
    workflow.advance(task_id, TaskState.PLANNED)

    def restore() -> None:
        set_task_store_for_tests(original_task_store)
        set_ledger_store_for_tests(original_ledger_store)

    return fresh_task_store, fresh_ledger_store, restore


class TestProcessRestartReplay:
    """A fresh orchestrator instance must rebuild state from the ledger."""

    def setup_method(self) -> None:
        ledger_store.reset()
        task_store.reset()

    def test_fresh_orchestrator_replays_inflight_state(self) -> None:
        workflow = WorkflowOrchestrator()
        workflow.register("task-replay", device_id="dev-1", task={"task_id": "task-replay", "device_id": "dev-1"})
        workflow.advance("task-replay", TaskState.PLANNED)
        workflow.advance("task-replay", TaskState.SIMULATED)
        workflow.advance("task-replay", TaskState.WAITING_APPROVAL)

        fresh_workflow = WorkflowOrchestrator()
        assert fresh_workflow.get_state("task-replay") == TaskState.WAITING_APPROVAL

    def test_fresh_orchestrator_replays_terminal_state(self) -> None:
        workflow = WorkflowOrchestrator()
        workflow.register("task-done", device_id="dev-1", task={"task_id": "task-done", "device_id": "dev-1"})
        for target in (
            TaskState.PLANNED,
            TaskState.SIMULATED,
            TaskState.READY_TO_DISPATCH,
            TaskState.DISPATCHED,
            TaskState.RUNNING,
            TaskState.TERMINAL,
        ):
            workflow.advance("task-done", target)

        fresh_workflow = WorkflowOrchestrator()
        assert fresh_workflow.get_state("task-done") == TaskState.TERMINAL

    def test_state_survives_ledger_store_instance_swap(self) -> None:
        """Simulate a new process attaching to a persisted ledger."""
        workflow = WorkflowOrchestrator()
        workflow.register("task-swap", device_id="dev-1", task={"task_id": "task-swap", "device_id": "dev-1"})
        workflow.advance("task-swap", TaskState.PLANNED)

        events = ledger_store.events_for_task("task-swap")
        new_store = InMemoryLedgerStore()
        for event in events:
            new_store.append_event(event)

        set_ledger_store_for_tests(new_store)
        try:
            fresh_workflow = WorkflowOrchestrator()
            assert fresh_workflow.get_state("task-swap") == TaskState.PLANNED
        finally:
            set_ledger_store_for_tests(InMemoryLedgerStore())


class TestRecoverInflightTasks:
    """recover_inflight_tasks scans task_store and replays ledger events."""

    def setup_method(self) -> None:
        ledger_store.reset()
        task_store.reset()

    def test_recover_counts_inflight_tasks(self) -> None:
        workflow = WorkflowOrchestrator()
        for idx, status in enumerate(["queued", "queued", "completed", "failed"]):
            task_id = f"task-{idx}"
            task = {"task_id": task_id, "device_id": "dev-1"}
            workflow.register(task_id, device_id="dev-1", task=task)
            if idx < 2:
                workflow.advance(task_id, TaskState.PLANNED)
            task_store.create_task_state(task, status=status)

        result = recover_inflight_tasks(task_store, workflow)

        assert result["scanned"] == 2
        assert result["recovered"] == 2
        assert result["missing_in_ledger"] == 0
        assert result["status_mismatch"] == 0

    def test_recover_reports_missing_in_ledger(self) -> None:
        task_store.create_task_state({"task_id": "orphan", "device_id": "dev-1"}, status="queued")

        result = recover_inflight_tasks(task_store, WorkflowOrchestrator())

        assert result["scanned"] == 1
        assert result["recovered"] == 0
        assert result["missing_in_ledger"] == 1

    def test_recover_reports_status_mismatch(self, caplog: pytest.LogCaptureFixture) -> None:
        workflow = WorkflowOrchestrator()
        task_id = "task-mismatch"
        task = {"task_id": task_id, "device_id": "dev-1"}
        workflow.register(task_id, device_id="dev-1", task=task)
        workflow.advance(task_id, TaskState.PLANNED)
        # "accepted" is an active store status but inconsistent with workflow PLANNED.
        task_store.create_task_state(task, status="accepted")

        with caplog.at_level(logging.WARNING):
            result = recover_inflight_tasks(task_store, workflow)

        assert result["scanned"] == 1
        assert result["recovered"] == 1
        assert result["status_mismatch"] == 1
        assert "status mismatch" in caplog.text

    def test_recover_respects_limit(self) -> None:
        workflow = WorkflowOrchestrator()
        for idx in range(5):
            task_id = f"task-limit-{idx}"
            task = {"task_id": task_id, "device_id": "dev-1"}
            workflow.register(task_id, device_id="dev-1", task=task)
            workflow.advance(task_id, TaskState.PLANNED)
            task_store.create_task_state(task, status="queued")

        result = recover_inflight_tasks(task_store, workflow, limit=2)

        assert result["scanned"] == 2


class TestLifespanStartupRecovery:
    """Lifespan startup triggers workflow recovery for in-flight tasks."""

    def test_lifespan_recovers_inflight_tasks(self, monkeypatch, caplog):
        """Pre-populated task_store + ledger are recovered during lifespan startup."""
        from server_dlc import app

        monkeypatch.setenv("LIMA_DEVICE_TASK_STORE", "memory")
        monkeypatch.setenv("LIMA_DEVICE_LEDGER_STORE", "memory")
        monkeypatch.setenv("LIMA_DEVICE_REDIS_URL", "")

        task_id = "lifespan-recover-1"
        fresh_task, fresh_ledger, restore = _prepare_inflight_stores(task_id)
        try:
            with (
                caplog.at_level(logging.INFO),
                patch(
                    "device_gateway.store.configure_task_store_from_env",
                    side_effect=lambda: set_task_store_for_tests(fresh_task),
                ),
                patch(
                    "device_ledger.store.configure_ledger_store_from_env",
                    side_effect=lambda: set_ledger_store_for_tests(fresh_ledger),
                ),
            ):
                with TestClient(app) as client:
                    resp = client.get("/health")
                    _wait_for_recovery_log(caplog)
                    assert workflow.get_state(task_id) == TaskState.PLANNED
        finally:
            restore()

        assert resp.status_code == 200
        assert "workflow startup recovery completed" in caplog.text
        match = re.search(
            r"workflow startup recovery completed: .*['\"]recovered['\"]:\s*(\d+)",
            caplog.text,
        )
        assert match, f"expected recovered count in log: {caplog.text}"
        assert int(match.group(1)) == 1
