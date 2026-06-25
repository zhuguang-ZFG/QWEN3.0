"""M6: Tests for device memory consolidation module."""

from __future__ import annotations

import time


MOCK_NOW = 2_000_000_000.0  # fixed deterministic timestamp for stable tests
import pytest

from device_memory.store import MemoryStore
from device_memory.schemas import MemoryEntry, MemoryType
from device_memory.consolidation import consolidate_task_episodes


def _make_episode(device_id: str, task_id: str, task_type: str, outcome: str) -> MemoryEntry:
    import json

    return MemoryEntry(
        id=f"ep-{task_id}",
        device_id=device_id,
        type=MemoryType.TASK_EPISODE,
        key=f"episode_{task_id}",
        value=json.dumps({"task_type": task_type, "outcome": outcome}),
        ttl_days=60,
        created_at=int(MOCK_NOW),
        source="device_task",
        confidence=1.0 if outcome == "success" else 0.3,
    )


def test_single_episode_no_consolidation():
    store = MemoryStore()
    store.create(_make_episode("dev-1", "t1", "creative", "success"))
    results = consolidate_task_episodes(store, "dev-1")
    assert results == []


def test_two_successes_create_confidence():
    store = MemoryStore()
    store.create(_make_episode("dev-1", "t1", "creative", "success"))
    store.create(_make_episode("dev-1", "t2", "creative", "success"))
    results = consolidate_task_episodes(store, "dev-1")
    assert len(results) == 1
    assert results[0].type == MemoryType.PROCEDURE_CONFIDENCE
    import json

    data = json.loads(results[0].value)
    assert data["success_rate"] == 1.0
    assert data["total_count"] == 2


def test_mixed_outcomes_lower_confidence():
    store = MemoryStore()
    store.create(_make_episode("dev-1", "t1", "creative", "success"))
    store.create(_make_episode("dev-1", "t2", "creative", "failure"))
    store.create(_make_episode("dev-1", "t3", "creative", "success"))
    results = consolidate_task_episodes(store, "dev-1")
    assert len(results) == 1
    import json

    data = json.loads(results[0].value)
    assert data["success_rate"] == pytest.approx(2 / 3, abs=0.01)
    assert data["total_count"] == 3


def test_different_task_types_separate_confidence():
    store = MemoryStore()
    store.create(_make_episode("dev-1", "t1", "creative", "success"))
    store.create(_make_episode("dev-1", "t2", "creative", "success"))
    store.create(_make_episode("dev-1", "t3", "control", "success"))
    store.create(_make_episode("dev-1", "t4", "control", "success"))
    results = consolidate_task_episodes(store, "dev-1")
    assert len(results) == 2
    types = {r.key for r in results}
    assert "conf_creative" in types
    assert "conf_control" in types


def test_cross_device_isolation():
    store = MemoryStore()
    store.create(_make_episode("dev-1", "t1", "creative", "success"))
    store.create(_make_episode("dev-1", "t2", "creative", "success"))
    # dev-2 has only 1 episode, shouldn't consolidate
    store.create(_make_episode("dev-2", "t3", "creative", "success"))

    results_dev1 = consolidate_task_episodes(store, "dev-1")
    results_dev2 = consolidate_task_episodes(store, "dev-2")
    assert len(results_dev1) == 1
    assert len(results_dev2) == 0


def test_disabled_episodes_are_skipped():
    store = MemoryStore()
    ep1 = _make_episode("dev-1", "t1", "creative", "success")
    ep2 = _make_episode("dev-1", "t2", "creative", "success")
    store.create(ep1)
    store.create(ep2)
    store.disable(ep1.id)
    results = consolidate_task_episodes(store, "dev-1")
    assert results == []  # only 1 active episode


def test_idempotent_no_duplicate_on_same_data():
    store = MemoryStore()
    store.create(_make_episode("dev-1", "t1", "creative", "success"))
    store.create(_make_episode("dev-1", "t2", "creative", "success"))
    r1 = consolidate_task_episodes(store, "dev-1")
    r2 = consolidate_task_episodes(store, "dev-1")
    assert len(r1) == 1
    assert len(r2) == 0  # no change, should be idempotent


def test_expired_episodes_are_skipped():
    store = MemoryStore()
    old_ep = MemoryEntry(
        id="ep-old",
        device_id="dev-1",
        type=MemoryType.TASK_EPISODE,
        key="episode_old",
        value='{"task_type": "creative", "outcome": "success"}',
        ttl_days=1,
        created_at=int(MOCK_NOW) - 86400 * 2,
        source="device_task",
        confidence=1.0,
    )
    store.create(old_ep)
    store.create(_make_episode("dev-1", "t2", "creative", "success"))
    results = consolidate_task_episodes(store, "dev-1")
    assert results == []  # only 1 non-expired episode


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: MOCK_NOW)
