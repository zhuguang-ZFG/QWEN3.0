import pytest

from device_gateway.tasks import (
    create_task_from_transcript,
    install_task_store_for_tests,
    mark_task_dispatched,
    record_motion_event,
    reset_tasks_for_tests,
)
from device_workflow.state import TaskState


@pytest.fixture(autouse=True)
def _reset_device_state():
    from device_artifacts.store import artifact_store
    from device_ledger.store import ledger_store

    install_task_store_for_tests()
    reset_tasks_for_tests()
    ledger_store.reset()
    artifact_store.reset()
    yield
    reset_tasks_for_tests()
    ledger_store.reset()
    artifact_store.reset()


def test_ledger_events_reject_duplicate_event_id():
    from device_ledger.events import DuplicateLedgerEvent, new_event
    from device_ledger.store import ledger_store

    event = new_event(
        event_type="task_created",
        task_id="task-1",
        device_id="dev-1",
        payload={"task": {"task_id": "task-1"}},
        event_id="evt-fixed",
    )

    ledger_store.append_event(event)

    with pytest.raises(DuplicateLedgerEvent):
        ledger_store.append_event(event)


def test_task_creation_records_replayable_event_and_preview_artifact():
    from device_artifacts.store import artifact_store
    from device_ledger.store import ledger_store

    task = create_task_from_transcript("dev-1", "write LiMa", request_id="req-1")

    events = ledger_store.events_for_task(task["task_id"])
    replay = ledger_store.replay_task(task["task_id"])
    artifacts = artifact_store.artifacts_for_task(task["task_id"])

    assert events[0].event_type == "task_created"
    assert "task_updated" in [event.event_type for event in events]
    assert events[-1].event_type == "task_updated"
    assert replay["task_id"] == task["task_id"]
    assert replay["device_id"] == "dev-1"
    assert replay["status"] in {"waiting_approval", "ready_to_dispatch"}
    assert replay["task"]["request_id"] == "req-1"
    assert [artifact.artifact_type for artifact in artifacts] == ["preview_svg", "route_evidence"]
    assert artifacts[0].content_hash
    assert artifacts[0].content.startswith("<svg")
    route_ev = artifacts[1]
    assert route_ev.content["route_role"] == "device_write"


def test_dispatch_records_task_dispatched_event():
    from device_ledger.store import ledger_store

    task = create_task_from_transcript("dev-1", "write one")
    mark_task_dispatched(task["task_id"])

    replay = ledger_store.replay_task(task["task_id"])
    event_types = [event.event_type for event in ledger_store.events_for_task(task["task_id"])]

    assert event_types[0] == "task_created"
    assert event_types[-1] == "task_dispatched"
    assert "task_updated" in event_types
    assert replay["status"] == "dispatched"


def test_motion_events_record_terminal_event_and_result_artifact():
    from device_artifacts.store import artifact_store
    from device_ledger.store import ledger_store
    from device_workflow.orchestrator import workflow

    task = create_task_from_transcript("dev-1", "write terminal")
    # Ensure the workflow is in a dispatchable state before recording motion events.
    if workflow.get_state(task["task_id"]) == TaskState.WAITING_APPROVAL:
        workflow.advance(task["task_id"], TaskState.READY_TO_DISPATCH)

    record_motion_event(
        {
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": task["task_id"],
            "phase": "accepted",
        }
    )
    record_motion_event(
        {
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": task["task_id"],
            "phase": "done",
            "final_position": {"x": 10, "y": 20, "z": 0},
        }
    )

    replay = ledger_store.replay_task(task["task_id"])
    artifacts = artifact_store.artifacts_for_task(task["task_id"], artifact_type="terminal_result")
    event_types = [event.event_type for event in ledger_store.events_for_task(task["task_id"])]

    assert "task_created" in event_types
    assert "motion_event" in event_types
    assert "task_terminal" in event_types
    assert event_types[-1] == "task_terminal"
    assert replay["status"] == "done"
    assert replay["terminal_event"]["phase"] == "done"
    assert len(artifacts) == 1
    assert artifacts[0].content["phase"] == "done"


def test_artifact_snapshots_are_copied():
    from device_artifacts.store import artifact_store

    artifact_store.put_artifact(
        task_id="task-1",
        artifact_type="terminal_result",
        content={"phase": "failed", "error": {"code": "E_STOP"}},
    )
    first = artifact_store.artifacts_for_task("task-1")
    first[0].content["phase"] = "mutated"

    assert artifact_store.artifacts_for_task("task-1")[0].content["phase"] == "failed"
