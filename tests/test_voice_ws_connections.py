"""Tests for per-account voice WebSocket connection limits."""

from __future__ import annotations

import voice_ws_connections


def test_try_acquire_respects_max_concurrent():
    voice_ws_connections.reset()
    assert voice_ws_connections.try_acquire("a-owner", max_concurrent=2) is True
    assert voice_ws_connections.try_acquire("a-owner", max_concurrent=2) is True
    assert voice_ws_connections.try_acquire("a-owner", max_concurrent=2) is False
    voice_ws_connections.release("a-owner")
    assert voice_ws_connections.try_acquire("a-owner", max_concurrent=2) is True


def test_release_clears_account_slot():
    voice_ws_connections.reset()
    voice_ws_connections.try_acquire("a-owner", max_concurrent=1)
    voice_ws_connections.release("a-owner")
    assert voice_ws_connections.count("a-owner") == 0
    assert voice_ws_connections.try_acquire("a-owner", max_concurrent=1) is True
