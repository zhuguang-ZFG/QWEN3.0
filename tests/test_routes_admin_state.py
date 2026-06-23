"""Tests for routes/admin_state.py."""

from __future__ import annotations

import threading

from routes import admin_state


def test_inject_state_updates_context():
    stats = {"total_requests": 0}
    lock = threading.Lock()
    enabled = {"backend-a": True}
    admin_state.inject_state(stats, lock, enabled)
    s, l, e = admin_state.stats_context()
    assert s is stats
    assert l is lock
    assert e is enabled
