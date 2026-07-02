"""M5: Tests for recovery phase gating (execute_recovery returns None for non-failed phases)."""

from __future__ import annotations

import pytest

from device_gateway.tasks import (
    execute_recovery,
    reset_tasks_for_tests,
)
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway import store as store_mod


@pytest.fixture(autouse=True)
def _isolate_store(monkeypatch):
    """Give each test a fresh in-memory store."""
    store = InMemoryDeviceTaskStore()
    monkeypatch.setattr(store_mod, "task_store", store)
    reset_tasks_for_tests()
    yield
    reset_tasks_for_tests()


class TestExecuteRecoveryNonePhase:
    def test_non_failed_phase_returns_none(self):
        result = execute_recovery("task-1", "dev-1", {"phase": "accepted", "task_id": "task-1"})
        assert result is None

    def test_running_phase_returns_none(self):
        result = execute_recovery("task-1", "dev-1", {"phase": "running", "task_id": "task-1"})
        assert result is None

    def test_no_error_code_returns_none(self):
        result = execute_recovery(
            "task-1",
            "dev-1",
            {
                "phase": "failed",
                "task_id": "task-1",
            },
        )
        assert result is None
