"""Tests for device ledger projections and activity endpoints."""

from __future__ import annotations

import pytest

from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding
from device_ledger.events import new_event
from device_ledger.projection import device_projection, task_projection
from device_ledger.store import ledger_store
from device_gateway.tasks import reset_tasks_for_tests


def _seed_device() -> None:
    seed_account_and_device()
    seed_binding()


def _record_task_lifecycle(task_id: str, device_id: str, terminal_phase: str) -> None:
    ledger_store.append_event(
        new_event(
            event_type="task_created",
            task_id=task_id,
            device_id=device_id,
            payload={"task": {"task_id": task_id, "device_id": device_id}, "status": "created"},
        )
    )
    ledger_store.append_event(
        new_event(
            event_type="task_dispatched",
            task_id=task_id,
            device_id=device_id,
            payload={"task_id": task_id},
        )
    )
    ledger_store.append_event(
        new_event(
            event_type="task_acknowledged",
            task_id=task_id,
            device_id=device_id,
            payload={},
        )
    )
    ledger_store.append_event(
        new_event(
            event_type="task_progress",
            task_id=task_id,
            device_id=device_id,
            payload={"progress": 42},
        )
    )
    ledger_store.append_event(
        new_event(
            event_type="motion_event",
            task_id=task_id,
            device_id=device_id,
            payload={"motion_event": {"phase": "running"}},
        )
    )
    ledger_store.append_event(
        new_event(
            event_type="task_terminal",
            task_id=task_id,
            device_id=device_id,
            payload={"terminal_event": {"phase": terminal_phase}},
        )
    )


def test_rebuild_state_transitions():
    reset_tasks_for_tests()
    task_id = "task-state-001"
    device_id = "dev-state-1"
    _record_task_lifecycle(task_id, device_id, "done")

    state = task_projection.rebuild_state(task_id)

    assert state["task_id"] == task_id
    assert state["device_id"] == device_id
    assert state["status"] == "done"
    assert state["progress"] == 42
    assert state["event_count"] == 6
    assert state["created_at"]
    assert state["last_event_at"]


def test_rebuild_state_pause_and_resume():
    reset_tasks_for_tests()
    task_id = "task-pause-001"
    device_id = "dev-pause-1"
    ledger_store.append_event(
        new_event(
            event_type="task_created",
            task_id=task_id,
            device_id=device_id,
            payload={"task": {"task_id": task_id, "device_id": device_id}, "status": "created"},
        )
    )
    ledger_store.append_event(new_event(event_type="task_paused", task_id=task_id, device_id=device_id, payload={}))
    ledger_store.append_event(new_event(event_type="task_resumed", task_id=task_id, device_id=device_id, payload={}))

    state = task_projection.rebuild_state(task_id)

    assert state["status"] == "resumed"


def test_timeline_order_matches_created_at():
    reset_tasks_for_tests()
    task_id = "task-timeline-001"
    device_id = "dev-timeline-1"
    for index, event_type in enumerate(["task_created", "task_dispatched", "task_terminal"]):
        payload = {"task": {"task_id": task_id, "device_id": device_id}, "status": "created"}
        if event_type == "task_terminal":
            payload = {"terminal_event": {"phase": "done"}}
        ledger_store.append_event(
            new_event(
                event_type=event_type,
                task_id=task_id,
                device_id=device_id,
                payload=payload,
                created_at=f"2026-01-01T00:00:0{index}Z",
            )
        )

    timeline = task_projection.timeline(task_id)

    assert len(timeline) == 3
    assert [event["event_type"] for event in timeline] == ["task_created", "task_dispatched", "task_terminal"]


def test_task_duration_calculates_intervals():
    reset_tasks_for_tests()
    task_id = "task-duration-001"
    device_id = "dev-duration-1"
    ledger_store.append_event(
        new_event(
            event_type="task_created",
            task_id=task_id,
            device_id=device_id,
            payload={"task": {"task_id": task_id, "device_id": device_id}, "status": "created"},
            created_at="2026-01-01T00:00:00Z",
        )
    )
    ledger_store.append_event(
        new_event(
            event_type="task_dispatched",
            task_id=task_id,
            device_id=device_id,
            payload={},
            created_at="2026-01-01T00:00:01Z",
        )
    )
    ledger_store.append_event(
        new_event(
            event_type="task_acknowledged",
            task_id=task_id,
            device_id=device_id,
            payload={},
            created_at="2026-01-01T00:00:03Z",
        )
    )
    ledger_store.append_event(
        new_event(
            event_type="task_terminal",
            task_id=task_id,
            device_id=device_id,
            payload={"terminal_event": {"phase": "done"}},
            created_at="2026-01-01T00:00:08Z",
        )
    )

    duration = task_projection.task_duration(task_id)

    assert duration is not None
    assert duration["total_ms"] == 8000
    assert duration["queue_ms"] == 1000
    assert duration["dispatch_ms"] == 2000
    assert duration["execute_ms"] == 5000


def test_device_summary_success_rate(tmp_path, monkeypatch):
    reset_tasks_for_tests()
    client = make_client(tmp_path, monkeypatch)[0]
    _seed_device()
    device_id = "dev-1"
    ledger_store.append_event(
        new_event(event_type="device_connected", task_id=device_id, device_id=device_id, payload={})
    )
    _record_task_lifecycle("task-summary-1", device_id, "done")
    _record_task_lifecycle("task-summary-2", device_id, "done")
    _record_task_lifecycle("task-summary-3", device_id, "failed")

    response = client.get(f"/device/v1/app/devices/{device_id}/activity", headers=headers("a-owner"))

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["device_id"] == device_id
    assert data["total_events"] > 0
    assert data["unique_tasks"] == 3  # three real tasks
    assert data["completed"] == 2
    assert data["failed"] == 1
    assert data["success_rate"] == pytest.approx(2 / 3, rel=1e-4)
    assert data["last_activity"]


def test_timeline_endpoint_returns_state_and_duration(tmp_path, monkeypatch):
    reset_tasks_for_tests()
    client, _store = make_client(tmp_path, monkeypatch)
    _seed_device()
    device_id = "dev-1"
    task_id = "task-timeline-endpoint-1"
    _record_task_lifecycle(task_id, device_id, "done")

    response = client.get(f"/device/v1/app/tasks/{task_id}/timeline", headers=headers("a-owner"))

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"]["task_id"] == task_id
    assert data["state"]["status"] == "done"
    assert len(data["timeline"]) == 6
    assert data["duration"] is not None
    assert data["duration"]["total_ms"] is not None


def test_timeline_endpoint_rejects_unauthorized_device(tmp_path, monkeypatch):
    reset_tasks_for_tests()
    client, _store = make_client(tmp_path, monkeypatch)
    _seed_device()
    task_id = "task-timeline-auth-1"
    _record_task_lifecycle(task_id, "dev-1", "done")

    response = client.get(f"/device/v1/app/tasks/{task_id}/timeline", headers=headers("a-other"))

    assert response.status_code == 403


def test_activity_endpoint_rejects_unauthorized_device(tmp_path, monkeypatch):
    reset_tasks_for_tests()
    client, _store = make_client(tmp_path, monkeypatch)
    _seed_device()

    response = client.get("/device/v1/app/devices/dev-1/activity", headers=headers("a-other"))

    assert response.status_code == 403
