"""dispatch write_text must send precomputed run_path, not NL re-parse only."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import rate_limiter
from device_gateway.tasks import DeviceTaskRequest, DeviceTaskRouteResult
from dlc_api.app import app
from dlc_api.deps import verify_dlc_api_token


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def _override_token() -> str:
    return "dev-1"


app.dependency_overrides[verify_dlc_api_token] = _override_token


@patch("dlc_core.dispatch.active_tasks_for_device", return_value=[])
@patch("dlc_api.motion_payload.handle_write", new_callable=AsyncMock)
@patch("dlc_core.dispatch.create_and_route_task", new_callable=AsyncMock)
def test_dispatch_write_text_sends_run_path(
    mock_create_route: AsyncMock,
    mock_write: AsyncMock,
    _mock_active: object,
) -> None:
    mock_write.return_value = {
        "status": "success",
        "path_data": [{"x": 1.0, "y": 2.0, "z": 0.0}, {"x": 3.0, "y": 4.0, "z": 0.0}],
        "preview_svg": "<svg/>",
        "width": 40,
        "height": 20,
        "model": "deterministic",
        "error": None,
    }
    mock_create_route.return_value = DeviceTaskRouteResult(
        status="queued_no_delivery",
        sent=False,
        queue_depth=1,
        task={"capability": "run_path", "task_id": "task-w1"},
    )
    response = TestClient(app).post(
        "/dlc/tasks/dispatch",
        json={
            "type": "write_text",
            "device_id": "dev-1",
            "payload": {"text": "你好"},
            "request_id": "req-write-1",
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "queued_no_delivery"
    mock_create_route.assert_awaited_once()
    req: DeviceTaskRequest = mock_create_route.await_args.args[0]
    assert req.voice_task is not None
    assert req.voice_task["capability"] == "run_path"
    assert req.voice_task["entrypoint"] == "write_text"
    assert req.voice_task["params"]["path"] == [
        {"x": 1.0, "y": 2.0, "z": 0.0},
        {"x": 3.0, "y": 4.0, "z": 0.0},
    ]
    assert req.text == "写你好"


def test_max_points_aligned_with_path_data() -> None:
    from device_gateway.path_data import MAX_PATH_POINTS
    from device_gateway.path_validator import MAX_PATH_POINTS as V_MAX
    from device_gateway.safety import MAX_POINTS

    assert MAX_POINTS == MAX_PATH_POINTS == V_MAX == 200
