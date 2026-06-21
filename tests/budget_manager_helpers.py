"""Test-only helpers for budget_manager in-process state."""

from __future__ import annotations

import budget_manager


def reset_budget_manager_state() -> None:
    with budget_manager._lock:
        budget_manager._usage.clear()
    budget_manager.reset_token_usage()


def set_budget_usage_for_tests(backend: str, used: int) -> None:
    with budget_manager._lock:
        budget_manager._check_reset()
        budget_manager._usage[backend] = used
