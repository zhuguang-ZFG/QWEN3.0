"""Event-based Session Log — structured event recording for observability.

Based on Google ADK Event-based Session pattern:
- Every request/routing/response/error is a typed Event
- Events are stored in-memory with optional persistence
- Supports replay, analysis, and debugging
- Enables observability without external monitoring tools
- Uses contextvars for async-safe request scoping
"""

import contextvars
import time
from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    REQUEST_RECEIVED = "request_received"
    IDE_DETECTED = "ide_detected"
    SCENARIO_CLASSIFIED = "scenario_classified"
    BACKEND_SELECTED = "backend_selected"
    REFLECTION_APPLIED = "reflection_applied"
    ENSEMBLE_STARTED = "ensemble_started"
    RESPONSE_RECEIVED = "response_received"
    RESPONSE_ERROR = "response_error"
    FALLBACK_TRIGGERED = "fallback_triggered"
    MEMORY_INJECTED = "memory_injected"


@dataclass
class Event:
    """A single structured event in the session log."""

    type: EventType
    timestamp: float
    data: dict = field(default_factory=dict)

    @property
    def age_ms(self) -> int:
        return int((time.time() - self.timestamp) * 1000)


class EventLog:
    """In-memory event log for a single session/request lifecycle."""

    def __init__(self, max_events: int = 500) -> None:
        self._events: list[Event] = []
        self._max = max_events

    def emit(self, event_type: EventType, **data) -> Event:
        """Record a new event."""
        event = Event(type=event_type, timestamp=time.time(), data=data)
        self._events.append(event)
        if len(self._events) > self._max:
            self._events = self._events[-self._max:]
        return event

    @property
    def events(self) -> list[Event]:
        return list(self._events)

    def filter_by_type(self, event_type: EventType) -> list[Event]:
        return [e for e in self._events if e.type == event_type]

    def last(self, n: int = 5) -> list[Event]:
        return self._events[-n:]

    def summary(self) -> dict:
        """Generate a summary of the event log for observability."""
        type_counts: dict[str, int] = {}
        for e in self._events:
            key = e.type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        errors = self.filter_by_type(EventType.RESPONSE_ERROR)
        fallbacks = self.filter_by_type(EventType.FALLBACK_TRIGGERED)

        return {
            "total_events": len(self._events),
            "type_counts": type_counts,
            "error_count": len(errors),
            "fallback_count": len(fallbacks),
            "last_event": self._events[-1].type.value if self._events else None,
        }

    def clear(self) -> None:
        self._events.clear()


# Async-safe request-scoped event log using contextvars
_request_log_var: contextvars.ContextVar[EventLog] = contextvars.ContextVar(
    "request_log", default=None
)


def get_request_log() -> EventLog:
    log = _request_log_var.get(None)
    if log is None:
        log = EventLog()
        _request_log_var.set(log)
    return log


def new_request_log() -> EventLog:
    """Create a fresh event log for a new request lifecycle."""
    log = EventLog()
    _request_log_var.set(log)
    return log
