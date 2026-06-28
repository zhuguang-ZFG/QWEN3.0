"""Planner recall: inject device memories into planning decisions."""

from __future__ import annotations

import json
import logging
from typing import Any

from device_memory.schemas import MemoryEntry, MemoryType

_log = logging.getLogger(__name__)
from device_memory.quality_gates import is_hard_safety, is_safe_for_recall
from device_memory.store import MemoryStoreBackend


def recall_planner_hints(store: MemoryStoreBackend, device_id: str) -> dict[str, Any]:
    """Build a planner hint dict from active device memories.

    Returns {key: value} for planner consumption. Hard safety paths
    (workspace bounds, feed limits, etc.) are NEVER overridden by memory.
    """
    hints: dict[str, Any] = {"preferences": {}, "warnings": [], "confidence": {}}

    for entry in store.list_by_device(device_id, include_expired=False):
        if not is_safe_for_recall(entry):
            continue

        if is_hard_safety(entry.key):
            continue  # never override hard safety

        if entry.type == MemoryType.PREFERENCE:
            hints["preferences"][entry.key] = entry.value
        elif entry.type == MemoryType.DEVICE_FAILURE:
            data = _parse_value(entry.value)
            hints["warnings"].append(
                {
                    "error_code": data.get("error_code", ""),
                    "reason": data.get("reason", ""),
                }
            )
        elif entry.type == MemoryType.PROCEDURE_CONFIDENCE:
            data = _parse_value(entry.value)
            task_type = data.get("task_type", "")
            hints["confidence"][task_type] = {
                "success_rate": data.get("success_rate", 0),
                "total_count": data.get("total_count", 0),
            }

    return hints


def get_preferred_feed_for_device(store: MemoryStoreBackend, device_id: str) -> float | None:
    """Recall a device's preferred feed rate, if set by user.

    Returns None if no preference exists, or if hard safety forbids it.
    """
    entry = store.recall(device_id, "feed_rate", MemoryType.PREFERENCE)
    if entry is None or not is_safe_for_recall(entry):
        return None
    # Feed rate preference is always clamped; hard safety applies to max_feed bound
    try:
        val = float(entry.value)
        return max(100.0, min(val, 3000.0))  # clamp to safe range
    except (ValueError, TypeError):
        return None


def get_device_failure_warnings(store: MemoryStoreBackend, device_id: str) -> list[dict[str, Any]]:
    """Get active failure warnings for a device to display to operator."""
    warnings: list[dict[str, Any]] = []
    for entry in store.list_by_device(device_id, include_expired=False):
        if entry.type != MemoryType.DEVICE_FAILURE or entry.disabled:
            continue
        data = _parse_value(entry.value)
        warnings.append(
            {
                "error_code": data.get("error_code", ""),
                "reason": data.get("reason", ""),
                "capability": data.get("capability", ""),
            }
        )
    return warnings


def _parse_value(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError) as exc:
        _log.warning("device_memory value parse failed: %s", exc)
    return {}
