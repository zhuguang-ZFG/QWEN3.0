from __future__ import annotations

from typing import Any

import pytest

from device_gateway.sessions import registry
from device_gateway.tasks import DeviceTaskRequest, create_and_route_task, pending_count, reset_tasks_for_tests


@pytest.fixture(autouse=True)
def _reset_device_state():
    registry.clear()
    reset_tasks_for_tests()
    yield
    registry.clear()
    reset_tasks_for_tests()


@pytest.mark.asyncio
async def test_create_and_route_task_queues_when_device_offline() -> None:
    result = await create_and_route_task(DeviceTaskRequest(device_id="dev-1", text="home", request_id="req-1"))

    assert result.status == "queued"
    assert result.sent is False
    assert result.queue_depth == 1
    assert result.task["device_id"] == "dev-1"
    assert result.task["type"] == "motion_task"
    assert pending_count("dev-1") == 1


@pytest.mark.asyncio
async def test_create_and_route_task_returns_failed_for_invalid_projection(monkeypatch) -> None:
    async def fake_create_task_from_transcript_async(
        device_id: str, text: str, request_id: str | None = None, **kwargs: Any
    ) -> dict:
        return {
            "type": "motion_task",
            "task_id": "task-invalid",
            "device_id": device_id,
            "capability": "run_path",
            "params": {},
            "error": {"code": "E_UNSUPPORTED_CAPABILITY", "reason": "unsupported"},
        }

    monkeypatch.setattr(
        "device_gateway.tasks.create_task_from_transcript_async",
        fake_create_task_from_transcript_async,
    )

    result = await create_and_route_task(DeviceTaskRequest(device_id="dev-1", text="invalid", request_id="req-2"))

    assert result.status == "failed"
    assert result.sent is False
    assert result.queue_depth == 0
    assert result.task["error"]["code"] == "E_UNSUPPORTED_CAPABILITY"
