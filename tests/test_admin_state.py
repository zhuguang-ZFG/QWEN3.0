"""Tests for routes/admin_state.py — admin shared state."""

import threading

from routes.admin_state import inject_state, stats_context


class TestAdminState:
    def test_initial_state(self):
        stats, lock, enabled = stats_context()
        assert isinstance(stats, dict)
        assert isinstance(lock, type(threading.Lock()))
        assert isinstance(enabled, dict)

    def test_inject_state(self):
        new_stats = {"a": 1}
        new_lock = threading.Lock()
        new_enabled = {"b": True}
        inject_state(new_stats, new_lock, new_enabled)
        stats, lock, enabled = stats_context()
        assert stats is new_stats
        assert lock is new_lock
        assert enabled is new_enabled
