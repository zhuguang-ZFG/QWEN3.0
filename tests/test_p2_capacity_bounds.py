"""Tests for P2 capacity bounds: eviction, drop-oldest, and warning on overflow."""

from __future__ import annotations

import logging
import queue
import time

import pytest

import device_logic.rate_limit as rl_mod
from device_logic.rate_limit import RateLimiter
from device_gateway import device_route_memory as drm
import rate_limiter as rl


# =========================================================================
# RateLimiter: _MAX_KEYS eviction (device_logic/rate_limit.py)
# =========================================================================


class TestRateLimiterCapacity:
    """Verify that RateLimiter evicts old keys when _MAX_KEYS is exceeded."""

    def test_evicts_oldest_when_over_capacity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fill RateLimiter beyond _MAX_KEYS; oldest key should be evicted."""
        monkeypatch.setattr(rl_mod.RateLimiter, "_MAX_KEYS", 3)
        limiter = RateLimiter(max_calls=5, window_seconds=300)

        # Insert 3 distinct keys
        assert limiter.is_allowed("k1") is True
        assert limiter.is_allowed("k2") is True
        assert limiter.is_allowed("k3") is True
        assert len(limiter._calls) == 3

        # Insert a 4th key; should trigger eviction of oldest ("k1")
        assert limiter.is_allowed("k4") is True
        assert "k1" not in limiter._calls
        assert len(limiter._calls) <= 3

    def test_new_key_allowed_after_eviction(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After eviction, the new key is fully usable (not rate-limited)."""
        monkeypatch.setattr(rl_mod.RateLimiter, "_MAX_KEYS", 2)
        limiter = RateLimiter(max_calls=5, window_seconds=300)

        limiter.is_allowed("ka")
        limiter.is_allowed("kb")
        # kb is the most recent, ka should be evicted when kc arrives
        assert limiter.is_allowed("kc") is True
        assert "ka" not in limiter._calls
        assert "kc" in limiter._calls

    def test_eviction_does_not_affect_recent_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only old keys are evicted; recently active keys remain usable."""
        monkeypatch.setattr(rl_mod.RateLimiter, "_MAX_KEYS", 3)
        limiter = RateLimiter(max_calls=5, window_seconds=300)
        # Use distinct timestamps so eviction order is deterministic.
        import time as _time

        t0 = _time.monotonic()
        monkeypatch.setattr(rl_mod.time, "monotonic", lambda: t0)
        limiter.is_allowed("a")  # t0
        limiter.is_allowed("b")  # t0
        limiter.is_allowed("c")  # t0
        # Re-activate "a" at a later timestamp
        monkeypatch.setattr(rl_mod.time, "monotonic", lambda: t0 + 10.0)
        limiter.is_allowed("a")  # t0+10
        # Insert "d" — should evict oldest by last-touch: "b" or "c"
        monkeypatch.setattr(rl_mod.time, "monotonic", lambda: t0 + 20.0)
        limiter.is_allowed("d")  # t0+20
        assert "a" in limiter._calls  # "a" was recently used (t0+10)
        assert "b" not in limiter._calls  # oldest (t0), evicted


# =========================================================================
# rate_limiter.py: _keyed_requests MAX_TRACKED_KEYS eviction
# =========================================================================


class TestKeyedRequestsCapacity:
    """Verify that _keyed_requests evicts oldest entries when exceeding MAX_TRACKED_KEYS."""

    def test_evicts_oldest_keyed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fill _keyed_requests beyond MAX_TRACKED_KEYS; oldest entries evicted."""
        monkeypatch.setattr(rl, "MAX_TRACKED_KEYS", 3)
        rl.reset()

        # Insert 3 keys
        rl.check_keyed_rate_limit("ka", max_per_window=10)
        rl.check_keyed_rate_limit("kb", max_per_window=10)
        rl.check_keyed_rate_limit("kc", max_per_window=10)
        assert len(rl._keyed_requests) == 3

        # Insert a 4th key — oldest ("ka") should be evicted
        rl.check_keyed_rate_limit("kd", max_per_window=10)
        assert "ka" not in rl._keyed_requests
        assert len(rl._keyed_requests) <= 3

    def test_oldest_key_evicted_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The key with the oldest last-touch timestamp is evicted first."""
        monkeypatch.setattr(rl, "MAX_TRACKED_KEYS", 2)
        rl.reset()

        rl.check_keyed_rate_limit("older", max_per_window=10)
        self._micro_sleep()
        rl.check_keyed_rate_limit("newer", max_per_window=10)
        self._micro_sleep()
        rl.check_keyed_rate_limit("third", max_per_window=10)
        # "older" has the oldest last-touch → evicted
        assert "older" not in rl._keyed_requests
        assert "newer" in rl._keyed_requests
        assert "third" in rl._keyed_requests

    def test_existing_key_not_counted_as_new(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Updating an existing key should not trigger eviction."""
        monkeypatch.setattr(rl, "MAX_TRACKED_KEYS", 2)
        rl.reset()

        rl.check_keyed_rate_limit("x", max_per_window=10)
        rl.check_keyed_rate_limit("y", max_per_window=10)
        # Update "x" again — should not evict anyone
        rl.check_keyed_rate_limit("x", max_per_window=10)
        assert "x" in rl._keyed_requests
        assert "y" in rl._keyed_requests
        assert len(rl._keyed_requests) == 2

    @staticmethod
    def _micro_sleep() -> None:
        time.sleep(0.005)


# =========================================================================
# device_route_memory.py: _MAX_RECORDS FIFO eviction
# =========================================================================


class TestRouteMemoryCapacity:
    """Verify that route memory FIFO-evicts oldest entries at _MAX_RECORDS."""

    def setup_method(self) -> None:
        drm.reset_route_memory_for_tests()

    def test_fifo_eviction_on_insert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Inserting beyond _MAX_RECORDS evicts the oldest entry."""
        monkeypatch.setattr(drm, "_MAX_RECORDS", 3)
        drm.reset_route_memory_for_tests()

        drm.record_route_decision("d1", "b1", True)
        drm.record_route_decision("d2", "b2", True)
        drm.record_route_decision("d3", "b3", True)
        assert len(drm._ROUTE_MEMORY) == 3

        # 4th insert should evict d1
        drm.record_route_decision("d4", "b4", True)
        assert "d1" not in drm._ROUTE_MEMORY
        assert len(drm._ROUTE_MEMORY) == 3

    def test_existing_device_update_no_eviction(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Updating an existing device should not change entry count."""
        monkeypatch.setattr(drm, "_MAX_RECORDS", 2)
        drm.reset_route_memory_for_tests()

        drm.record_route_decision("d1", "b1", True)
        drm.record_route_decision("d2", "b2", True)
        # Update d1
        drm.record_route_decision("d1", "b1", True)
        assert len(drm._ROUTE_MEMORY) == 2

    def test_fifo_order_maintained(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Oldest (first inserted) entry should always be evicted first."""
        monkeypatch.setattr(drm, "_MAX_RECORDS", 2)
        drm.reset_route_memory_for_tests()

        drm.record_route_decision("dev1", "b1", True)
        drm.record_route_decision("dev2", "b2", True)
        drm.record_route_decision("dev3", "b3", True)
        assert "dev1" not in drm._ROUTE_MEMORY
        assert "dev2" in drm._ROUTE_MEMORY
        assert "dev3" in drm._ROUTE_MEMORY


# =========================================================================
# structured_logging.py: _BoundedQueueHandler drop-oldest
# =========================================================================


class TestBoundedQueueHandler:
    """Verify that _BoundedQueueHandler drops oldest records when full."""

    def _make_handler(self, maxsize: int = 5) -> tuple:
        """Create a _BoundedQueueHandler with a small queue for testing."""
        from observability.structured_logging import _BoundedQueueHandler

        q: queue.Queue[logging.LogRecord] = queue.Queue(maxsize)
        handler = _BoundedQueueHandler(q)
        return handler, q

    def test_drops_oldest_when_full(self) -> None:
        """When queue is full, the oldest record is dropped to make room."""
        handler, q = self._make_handler(3)
        logger = logging.getLogger("test_drop")

        # Fill queue past capacity
        for i in range(5):
            record = logger.makeRecord(
                logger.name,
                logging.INFO,
                "test.py",
                i + 1,
                f"msg-{i}",
                (),
                None,
            )
            handler.enqueue(record)

        # Queue should have at most 3 items (oldest 2 were dropped)
        assert q.qsize() <= 3

    def test_latest_records_preserved(self) -> None:
        """The most recent records should survive after oldest are dropped."""
        handler, q = self._make_handler(3)
        logger = logging.getLogger("test_preserve")

        # Enqueue 5 records
        for i in range(5):
            record = logger.makeRecord(
                logger.name,
                logging.INFO,
                "test.py",
                i + 1,
                f"msg-{i}",
                (),
                None,
            )
            handler.enqueue(record)

        # Check that recent messages are in the queue
        remaining = []
        while not q.empty():
            remaining.append(q.get_nowait().getMessage())
        assert "msg-2" in remaining
        assert "msg-3" in remaining
        assert "msg-4" in remaining

    def test_handler_does_not_block(self) -> None:
        """enqueue should never block even when queue is repeatedly filled."""
        handler, q = self._make_handler(2)
        logger = logging.getLogger("test_noblock")

        for _ in range(100):
            record = logger.makeRecord(
                logger.name,
                logging.INFO,
                "test.py",
                1,
                "x",
                (),
                None,
            )
            handler.enqueue(record)

        assert q.qsize() <= 2
