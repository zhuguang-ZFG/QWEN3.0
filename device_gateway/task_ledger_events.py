"""Ledger event recorders for task and device lifecycle transitions.

Thin wrappers that append typed events to the device ledger. Extracted from
task_events.py to keep that module under the 300-line file limit.
"""

from __future__ import annotations

from typing import Any

from device_ledger.events import new_event
from device_ledger.store import ledger_store


def record_task_acknowledged(task_id: str, device_id: str, payload: dict[str, Any] | None = None) -> None:
    ledger_store.append_event(
        new_event(
            event_type="task_acknowledged",
            task_id=task_id,
            device_id=device_id,
            payload=payload or {},
        )
    )


def record_task_progress(
    task_id: str,
    device_id: str,
    progress: int = 0,
    payload: dict[str, Any] | None = None,
) -> None:
    merged = dict(payload or {})
    merged["progress"] = progress
    ledger_store.append_event(
        new_event(
            event_type="task_progress",
            task_id=task_id,
            device_id=device_id,
            payload=merged,
        )
    )


def record_task_paused(task_id: str, device_id: str) -> None:
    ledger_store.append_event(
        new_event(
            event_type="task_paused",
            task_id=task_id,
            device_id=device_id,
            payload={},
        )
    )


def record_task_resumed(task_id: str, device_id: str) -> None:
    ledger_store.append_event(
        new_event(
            event_type="task_resumed",
            task_id=task_id,
            device_id=device_id,
            payload={},
        )
    )


def record_device_connected(device_id: str) -> None:
    ledger_store.append_event(
        new_event(
            event_type="device_connected",
            task_id=device_id,
            device_id=device_id,
            payload={},
        )
    )


def record_device_disconnected(device_id: str) -> None:
    ledger_store.append_event(
        new_event(
            event_type="device_disconnected",
            task_id=device_id,
            device_id=device_id,
            payload={},
        )
    )
