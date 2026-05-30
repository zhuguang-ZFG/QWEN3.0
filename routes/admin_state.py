"""Shared mutable state for admin routes (CQ-014 slice 11)."""

from __future__ import annotations

import threading

from routes.request_tracking import FALLBACK_LOG as FALLBACK_LOG


_stats: dict = {}
_stats_lock: threading.Lock = threading.Lock()
_backend_enabled: dict = {}


def inject_state(stats: dict, stats_lock: threading.Lock, backend_enabled: dict) -> None:
    global _stats, _stats_lock, _backend_enabled
    _stats = stats
    _stats_lock = stats_lock
    _backend_enabled = backend_enabled


def stats_context() -> tuple[dict, threading.Lock, dict]:
    return _stats, _stats_lock, _backend_enabled
