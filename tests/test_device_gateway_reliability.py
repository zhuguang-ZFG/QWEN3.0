"""M5: Integration tests for device gateway reliability (reconnect, idempotency, failure injection)."""

from __future__ import annotations

import pytest

from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import (
    active_tasks_for_device,
    create_task_from_transcript,
    reset_tasks_for_tests,
    task_snapshot,
)
from device_ledger.events import new_event
from device_ledger.store import ledger_store
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState


class DummyWebSocket:
    def __init__(self):
        self.sent = []
        self._open = True

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self, code=1000):
        self._open = False


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=test-token")
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    reset_tasks_for_tests()
    registry.clear()
    yield
    reset_tasks_for_tests()
    registry.clear()


class TestTaskIdempotency:
    def test_create_task_creates_exactly_one(self):
        task = create_task_from_transcript("dev-1", "写你好")
        assert task["task_id"]
        snap = task_snapshot(task["task_id"])
        assert snap is not None
        assert snap["status"] == "created"

    def test_dispatched_task_shows_active(self):
        task = create_task_from_transcript("dev-1", "写你好")
        from device_gateway.tasks import record_motion_event

        record_motion_event(
            {
                "type": "motion_event",
                "device_id": "dev-1",
                "task_id": task["task_id"],
                "phase": "accepted",
            }
        )
        active = active_tasks_for_device("dev-1")
        assert len(active) >= 1
        task_ids = [t["task_id"] for t in active]
        assert task["task_id"] in task_ids

    def test_different_device_no_cross_talk(self):
        create_task_from_transcript("dev-1", "写你好")
        active_dev2 = active_tasks_for_device("dev-2")
        assert active_dev2 == []


class TestSessionReattach:
    def test_take_outstanding_tasks_transfers_and_clears(self):
        ws = DummyWebSocket()
        session = DeviceSession(device_id="dev-1", websocket=ws)
        session.mark_task_dispatched({"task_id": "task-001", "device_id": "dev-1"})
        session.mark_task_dispatched({"task_id": "task-002", "device_id": "dev-1"})

        taken = session.take_outstanding_tasks()
        assert len(taken) == 2
        assert len(session.outstanding_tasks()) == 0

    def test_reattach_avoids_duplicate_task_ids(self):
        ws = DummyWebSocket()
        session = DeviceSession(device_id="dev-1", websocket=ws)
        session.mark_task_dispatched({"task_id": "task-001", "device_id": "dev-1"})

        tasks_to_attach = [
            {"task_id": "task-001", "device_id": "dev-1"},
            {"task_id": "task-002", "device_id": "dev-1"},
        ]
        seen = set(session.inflight_tasks)
        attached = []
        for task in tasks_to_attach:
            tid = task["task_id"]
            if tid not in seen:
                session.mark_task_dispatched(task)
                seen.add(tid)
                attached.append(tid)

        assert attached == ["task-002"]


class TestRecoveryLedgerRecording:
    def test_device_reconnected_event_is_recorded(self):
        ledger_store.append_event(
            new_event(
                event_type="motion_event",
                task_id="task-reconnect",
                device_id="dev-1",
                payload={
                    "motion_event": {
                        "type": "motion_event",
                        "device_id": "dev-1",
                        "task_id": "task-reconnect",
                        "phase": "device_reconnected",
                    }
                },
            )
        )
        events = ledger_store.events_for_task("task-reconnect")
        assert len(events) == 1
        payload = events[0].payload.get("motion_event", {})
        assert payload.get("phase") == "device_reconnected"

    def test_failed_event_stores_recovery_action(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        from device_gateway.tasks import record_motion_event

        record_motion_event(
            {
                "type": "motion_event",
                "device_id": "dev-1",
                "task_id": task_id,
                "phase": "failed",
                "error": {"code": "E_MISSING_PATH", "reason": "path missing"},
            }
        )

        events = ledger_store.events_for_task(task_id)
        recovery_found = any("recovery" in e.payload for e in events)
        assert recovery_found, "failed event should record recovery action in ledger"


class TestWorkflowRecovery:
    def test_recovering_transition_from_running(self):
        workflow.register("task-wf-recover")
        for s in (
            TaskState.PLANNED,
            TaskState.SIMULATED,
            TaskState.READY_TO_DISPATCH,
            TaskState.DISPATCHED,
            TaskState.RUNNING,
        ):
            workflow.advance("task-wf-recover", s)

        workflow.advance("task-wf-recover", TaskState.RECOVERING)
        workflow.advance("task-wf-recover", TaskState.RUNNING)
        assert workflow.get_state("task-wf-recover") == TaskState.RUNNING
