"""Typed event records for replaying device task history."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

EVENT_TYPES = frozenset(
    {
        "task_created",
        "task_dispatched",
        "motion_event",
        "task_terminal",
        "task_acknowledged",
        "task_progress",
        "task_paused",
        "task_resumed",
        "device_connected",
        "device_disconnected",
    }
)


class DuplicateLedgerEvent(ValueError):
    """Raised when an append-only ledger receives an event id twice."""


@dataclass(frozen=True)
class LedgerEvent:
    event_id: str
    event_type: str
    task_id: str
    device_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id is required")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported ledger event type: {self.event_type}")
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.created_at:
            object.__setattr__(self, "created_at", _now_iso())
        object.__setattr__(self, "payload", deepcopy(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "task_id": self.task_id,
            "device_id": self.device_id,
            "payload": deepcopy(self.payload),
            "created_at": self.created_at,
        }


def new_event(
    *,
    event_type: str,
    task_id: str,
    device_id: str,
    payload: dict[str, Any] | None = None,
    event_id: str | None = None,
    created_at: str | None = None,
) -> LedgerEvent:
    return LedgerEvent(
        event_id=event_id or f"ledger-{uuid.uuid4().hex}",
        event_type=event_type,
        task_id=task_id,
        device_id=device_id,
        payload=payload or {},
        created_at=created_at or _now_iso(),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
