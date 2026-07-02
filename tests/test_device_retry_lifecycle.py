"""M5: Tests for retry count tracking and exhaustion behavior."""

from __future__ import annotations

import pytest

from device_gateway.tasks import (
    create_task_from_transcript,
    execute_recovery,
    reset_tasks_for_tests,
    task_snapshot,
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


class TestRetryCountTracking:
    def test_retry_count_increments(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        # First failure
        r1 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        assert r1["attempt"] == 1

        # Second failure
        r2 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        assert r2["attempt"] == 2

        # Third failure
        r3 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        assert r3["attempt"] == 3

    def test_retry_count_persisted_in_snapshot(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )

        snap = task_snapshot(task_id)
        assert snap is not None
        assert snap.get("retry_count") == 2


class TestRetryExhaustion:
    def test_e_missing_path_exhausted_after_3_retries(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        for i in range(4):
            result = execute_recovery(
                task_id,
                "dev-1",
                {
                    "phase": "failed",
                    "task_id": task_id,
                    "error": {"code": "E_MISSING_PATH"},
                },
            )
            assert result is not None

        # 4th attempt (index 3) should stop, not retry
        r4 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        assert r4 is not None
        # After 4 increments, attempt=5, but should_retry(attempt-1=4) with max_retries=3 → False
        assert r4["action"] == "stop"
        assert "task" not in r4

    def test_e_limit_exhausted_after_1_retry(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        # First: retry
        r1 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_LIMIT"},
            },
        )
        assert r1["action"] == "retry"

        # Second: exhausted
        r2 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_LIMIT"},
            },
        )
        assert r2 is not None
        assert r2["action"] == "stop"
        assert "task" not in r2
