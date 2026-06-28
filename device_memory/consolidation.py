"""Consolidation: build procedure confidence from repeated task episodes."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from device_memory.schemas import MemoryEntry, MemoryType
from device_memory.store import MemoryStoreBackend

_log = logging.getLogger(__name__)


def _load_task_episodes(store: MemoryStoreBackend, device_id: str) -> list[dict[str, Any]]:
    """Return parsed, non-disabled TASK_EPISODE entries for *device_id*."""
    episodes = [
        e
        for e in store.list_by_device(device_id, include_expired=False)
        if e.type == MemoryType.TASK_EPISODE and not e.disabled
    ]
    return [_parse_episode_value(ep.value) for ep in episodes]


def _group_episodes_by_task_type(episodes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group episode data by `task_type` (default 'unknown')."""
    by_type: dict[str, list[dict[str, Any]]] = {}
    for data in episodes:
        task_type = data.get("task_type", "unknown")
        by_type.setdefault(task_type, []).append(data)
    return by_type


def _should_update_confidence(
    store: MemoryStoreBackend,
    device_id: str,
    existing_key: str,
    total: int,
    success_rate: float,
) -> bool:
    """Return True if the stored confidence entry differs from the new metrics."""
    old = store.recall(device_id, existing_key, MemoryType.PROCEDURE_CONFIDENCE)
    if old is None or not old.value:
        return True
    try:
        old_data = json.loads(old.value)
    except json.JSONDecodeError as exc:
        _log.warning(
            "device=%s key=%s corrupt procedure confidence value: %s",
            device_id,
            existing_key,
            exc,
        )
        return True
    old_rate = old_data.get("success_rate", 0)
    old_total = old_data.get("total_count", 0)
    return not (old_total == total and abs(old_rate - success_rate) < 0.01)


def _build_confidence_entry(
    device_id: str,
    task_type: str,
    items: list[dict[str, Any]],
    store: MemoryStoreBackend,
) -> MemoryEntry | None:
    """Create and persist a procedure-confidence entry if metrics changed."""
    total = len(items)
    successes = sum(1 for d in items if d.get("outcome") == "success")
    if total < 2:
        return None

    success_rate = successes / total
    confidence = _compute_confidence(total, successes)
    existing_key = f"conf_{task_type}"

    if not _should_update_confidence(store, device_id, existing_key, total, success_rate):
        return None

    entry = MemoryEntry(
        id=f"conf-{device_id}-{task_type}",
        device_id=device_id,
        type=MemoryType.PROCEDURE_CONFIDENCE,
        key=existing_key,
        value=json.dumps(
            {
                "task_type": task_type,
                "success_rate": round(success_rate, 3),
                "total_count": total,
                "confidence": round(confidence, 3),
            }
        ),
        ttl_days=90,
        created_at=int(time.time()),
        source="consolidation",
        confidence=round(confidence, 3),
    )
    store.create(entry)
    return entry


def consolidate_task_episodes(store: MemoryStoreBackend, device_id: str) -> list[MemoryEntry]:
    """Analyze task episodes for a device and produce/update procedure-confidence memories.

    Returns any newly created or updated confidence entries.
    """
    episodes = _load_task_episodes(store, device_id)
    if len(episodes) < 2:
        return []

    by_type = _group_episodes_by_task_type(episodes)
    results: list[MemoryEntry] = []
    for task_type, items in by_type.items():
        entry = _build_confidence_entry(device_id, task_type, items, store)
        if entry is not None:
            results.append(entry)

    return results


def _compute_confidence(total: int, successes: int) -> float:
    """Confidence grows with volume and success rate."""
    base_rate = successes / max(total, 1)
    # Volume factor: 2 episodes = 0.3, 10+ = 0.9
    volume_factor = min(0.9, max(0.1, total / 12.0))
    return round(base_rate * 0.7 + volume_factor * 0.3, 3)


def _parse_episode_value(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError) as exc:
        _log.warning("device_memory episode value parse failed: %s", exc)
    return {}
