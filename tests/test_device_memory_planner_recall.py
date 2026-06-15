"""M6: Tests for device memory recall (planner hints + failure warnings)."""

from __future__ import annotations

import json
import time

from device_memory.store import MemoryStore
from device_memory.schemas import MemoryEntry, MemoryType
from device_memory.recall import (
    recall_planner_hints,
    get_preferred_feed_for_device,
    get_device_failure_warnings,
)


def _mk_entry(device_id: str, eid: str, mtype: MemoryType, key: str, value: str,
              confidence: float = 1.0, disabled: bool = False) -> MemoryEntry:
    return MemoryEntry(
        id=eid, device_id=device_id, type=mtype, key=key, value=value,
        ttl_days=30, created_at=int(time.time()), source="test",
        confidence=confidence, disabled=disabled,
    )


class TestRecallPlannerHints:
    def test_preferences_in_hints(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "p1", MemoryType.PREFERENCE, "favorite_color",
                               "blue", confidence=0.8))
        hints = recall_planner_hints(store, "dev-1")
        assert hints["preferences"]["favorite_color"] == "blue"

    def test_device_failures_in_warnings(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "d1", MemoryType.DEVICE_FAILURE,
                               "failure_E_LIMIT",
                               json.dumps({"error_code": "E_LIMIT", "reason": "limit hit"}),
                               confidence=0.9))
        hints = recall_planner_hints(store, "dev-1")
        assert len(hints["warnings"]) == 1
        assert hints["warnings"][0]["error_code"] == "E_LIMIT"

    def test_procedure_confidence_in_hints(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "c1", MemoryType.PROCEDURE_CONFIDENCE,
                               "conf_creative",
                               json.dumps({"task_type": "creative", "success_rate": 0.85, "total_count": 10}),
                               confidence=0.8))
        hints = recall_planner_hints(store, "dev-1")
        assert hints["confidence"]["creative"]["success_rate"] == 0.85

    def test_disabled_memory_not_recalled(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "p1", MemoryType.PREFERENCE, "color",
                               "red", confidence=0.8, disabled=True))
        hints = recall_planner_hints(store, "dev-1")
        assert len(hints["preferences"]) == 0

    def test_low_confidence_not_recalled(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "p1", MemoryType.PREFERENCE, "color",
                               "red", confidence=0.3))
        hints = recall_planner_hints(store, "dev-1")
        assert len(hints["preferences"]) == 0

    def test_hard_safety_not_overridden(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "s1", MemoryType.PREFERENCE, "max_feed",
                               "5000", confidence=0.9))
        hints = recall_planner_hints(store, "dev-1")
        assert "max_feed" not in hints["preferences"]  # hard safety wins

    def test_cross_device_isolation(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "p1", MemoryType.PREFERENCE, "color", "red"))
        hints = recall_planner_hints(store, "dev-2")
        assert len(hints["preferences"]) == 0
        assert len(hints["warnings"]) == 0


class TestPreferredFeed:
    def test_valid_feed_recalled(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "f1", MemoryType.PREFERENCE, "feed_rate",
                               "800", confidence=0.8))
        feed = get_preferred_feed_for_device(store, "dev-1")
        assert feed == 800.0

    def test_feed_clamped_to_safe_range(self):
        # Test max clamp: feed=5000 → clamp to 3000
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "f1", MemoryType.PREFERENCE, "feed_rate",
                               "5000", confidence=0.8))
        feed = get_preferred_feed_for_device(store, "dev-1")
        assert feed == 3000.0

    def test_feed_clamped_to_min(self):
        # Test min clamp: feed=50 → clamp to 100
        store = MemoryStore()
        store.create(_mk_entry("dev-2", "f2", MemoryType.PREFERENCE, "feed_rate",
                               "50", confidence=0.8))
        feed = get_preferred_feed_for_device(store, "dev-2")
        assert feed == 100.0

    def test_no_preference_returns_none(self):
        store = MemoryStore()
        feed = get_preferred_feed_for_device(store, "dev-1")
        assert feed is None

    def test_hard_safety_blocks_feed_recall(self):
        store = MemoryStore()
        # feed_rate is NOT a hard safety path; hard safety paths are motion limits
        # like max_feed, max_path_points, workspace_bounds.
        # feed_rate preferences ARE safely recalled (clamped to 100-3000 range)
        store.create(_mk_entry("dev-1", "f1", MemoryType.PREFERENCE, "feed_rate",
                               "800", confidence=0.8))
        feed = get_preferred_feed_for_device(store, "dev-1")
        assert feed == 800.0  # feed_rate is soft preference, NOT hard safety


class TestFailureWarnings:
    def test_active_warnings_returned(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "d1", MemoryType.DEVICE_FAILURE,
                               "failure_E_LIMIT",
                               json.dumps({"error_code": "E_LIMIT", "reason": "hit"}), confidence=0.8))
        warnings = get_device_failure_warnings(store, "dev-1")
        assert len(warnings) == 1
        assert warnings[0]["error_code"] == "E_LIMIT"

    def test_disabled_failures_not_returned(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "d1", MemoryType.DEVICE_FAILURE,
                               "failure_E_LIMIT",
                               json.dumps({"error_code": "E_LIMIT", "reason": "hit"}),
                               confidence=0.8, disabled=True))
        warnings = get_device_failure_warnings(store, "dev-1")
        assert len(warnings) == 0

    def test_non_failure_types_not_returned(self):
        store = MemoryStore()
        store.create(_mk_entry("dev-1", "p1", MemoryType.PREFERENCE, "color", "red"))
        warnings = get_device_failure_warnings(store, "dev-1")
        assert len(warnings) == 0
