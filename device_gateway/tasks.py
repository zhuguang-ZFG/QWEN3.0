"""Device task projection helpers and store facade (public API)."""

from __future__ import annotations

from device_ledger.store import ledger_store

from . import store as store_mod
from .store import DeviceTaskStore, InMemoryDeviceTaskStore
from .task_creation import (
    create_task_from_transcript,
    create_task_from_transcript_async,
    project_to_motion_task,
    project_to_motion_task_async,
)
from .task_events import TERMINAL_PHASES, execute_recovery, record_motion_event
from .task_lifecycle import (
    ack_processing_task,
    active_tasks_for_device,
    enqueue_pending_task,
    mark_task_dispatched,
    pending_count,
    pop_pending_tasks,
    recover_stale_processing,
    remove_pending_task,
    requeue_pending_tasks,
    task_snapshot,
)
from . import task_deps

# Backward-compatible monkeypatch surface (tests patch device_gateway.tasks.*)
resolve_device_route_policy = task_deps.resolve_device_route_policy
validate_route_policy = task_deps.validate_route_policy
validate_capability_params = task_deps.validate_capability_params
resolve_profile = task_deps.resolve_profile
apply_profile_constraints = task_deps.apply_profile_constraints
policy_engine = task_deps.policy_engine

__all__ = [
    "TERMINAL_PHASES",
    "ack_processing_task",
    "active_tasks_for_device",
    "create_task_from_transcript",
    "create_task_from_transcript_async",
    "enqueue_pending_task",
    "execute_recovery",
    "install_task_store_for_tests",
    "mark_task_dispatched",
    "pending_count",
    "pop_pending_tasks",
    "project_to_motion_task",
    "project_to_motion_task_async",
    "record_motion_event",
    "recover_stale_processing",
    "remove_pending_task",
    "requeue_pending_tasks",
    "reset_tasks_for_tests",
    "task_snapshot",
]


def reset_tasks_for_tests() -> None:
    from device_artifacts.store import artifact_store

    store_mod.task_store.reset()
    ledger_store.reset()
    artifact_store.reset()
    from device_workflow.orchestrator import workflow

    workflow.reset()


def install_task_store_for_tests(store: DeviceTaskStore | None = None) -> DeviceTaskStore:
    selected = store or InMemoryDeviceTaskStore()
    store_mod.set_task_store_for_tests(selected)
    return selected
