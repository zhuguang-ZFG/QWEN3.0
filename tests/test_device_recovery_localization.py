"""M5: Tests for Chinese explanation in recovery results."""

from __future__ import annotations

import pytest

from device_gateway.tasks import (
    create_task_from_transcript,
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


class TestExplanationZh:
    def test_explanation_zh_in_result(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        result = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_ESTOP"},
            },
        )
        assert result is not None
        assert "explanation_zh" in result
        assert "急停" in result["explanation_zh"]
