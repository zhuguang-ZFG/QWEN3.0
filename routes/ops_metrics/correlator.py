"""Ops metrics correlator — cross-system trace by request/task/device id."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def correlate_by_id(target: str, limit: int = 50) -> list[dict[str, Any]]:
    """Correlate events by request_id, task_id, or device_id."""
    try:
        from observability.correlation import correlate_by_id as _correlate

        return _correlate(target, limit=limit)
    except ImportError:
        return []


def correlate_recent(limit: int = 10) -> list[dict[str, Any]]:
    """Get recent correlation events."""
    try:
        from observability.correlation import correlate_recent as _recent

        return _recent(limit)
    except ImportError:
        return []


def correlation_summary() -> dict[str, Any]:
    """Get correlation summary."""
    try:
        from observability.correlation import correlation_summary as _summary

        return _summary()
    except ImportError:
        return {"error": "correlation module not loaded"}


def build_trace(target: str) -> dict[str, Any]:
    """Build a trace timeline for a target id with cross-references."""
    matched = correlate_by_id(target)
    if not matched:
        recent = correlate_recent(10)
        return {
            "target": target,
            "matched": [],
            "hint": "no events found for this id",
            "recent_events": recent,
        }

    # Build a trace timeline with cross-references
    trace: list[dict] = []
    seen_ids: set[str] = set()
    for event in matched:
        trace.append(event)
        for key in ("request_id", "task_id", "device_id"):
            eid = event.get(key, "")
            if eid and eid != target and eid not in seen_ids:
                seen_ids.add(eid)

    # Pull in related events for discovered ids
    for related_id in list(seen_ids)[:5]:
        for event in correlate_by_id(related_id, limit=10):
            if event not in trace:
                trace.append(event)

    trace.sort(key=lambda e: e.get("ts", 0))
    return {
        "target": target,
        "matched_count": len(matched),
        "related_ids": sorted(seen_ids),
        "trace": trace,
    }
