"""Regression tests for RT-W1/RT-W2 (2026-07-20 round-2 review).

RT-W1: execute_task_template must be rate limited (same per-account budget as
create_task). RT-W2: batch_draw must be rate limited and cap the raw SVG size.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from routes import device_app_task_templates as templates
from routes import device_app_tasks as tasks

_ACCOUNT = {"id": "acc-1", "phone": "12345678901", "role": "user"}
_AUTH = {"Authorization": "Bearer test-token"}


def _limited_response() -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": {"message": "Rate limit exceeded. Try again later.", "type": "rate_limit_error"}},
    )


@pytest.fixture
def templates_client():
    app = FastAPI()
    app.include_router(templates.router)
    return TestClient(app)


@pytest.fixture
def tasks_client():
    app = FastAPI()
    app.include_router(tasks.router)
    return TestClient(app)


def test_execute_template_rate_limited(templates_client):
    with (
        patch.object(templates, "authorize", return_value=_ACCOUNT),
        patch.object(templates, "check_key_limit", return_value=_limited_response()) as mock_limit,
        patch.object(templates, "connect") as mock_connect,
    ):
        response = templates_client.post("/device/v1/app/tasks/templates/t-1/execute", json={}, headers=_AUTH)
    assert response.status_code == 429
    assert response.json()["error"]["type"] == "rate_limit_error"
    mock_limit.assert_called_once()
    assert mock_limit.call_args.args[0] == "device_app_task:acc-1"
    mock_connect.assert_not_called()  # limited before any DB work


def test_batch_draw_rate_limited(tasks_client):
    with (
        patch.object(tasks, "authorize", return_value=_ACCOUNT),
        patch.object(tasks, "check_key_limit", return_value=_limited_response()) as mock_limit,
        patch.object(tasks, "MultiDeviceCoordinator") as mock_coord,
    ):
        response = tasks_client.post(
            "/device/v1/app/devices/batch-draw",
            json={"device_ids": ["d-1"], "svg": "<svg/>", "coordinator_id": "c-1"},
            headers=_AUTH,
        )
    assert response.status_code == 429
    assert mock_limit.call_args.args[0] == "device_app_task:acc-1"
    mock_coord.assert_not_called()


def test_batch_draw_rejects_oversized_svg(tasks_client):
    huge_svg = "x" * (tasks._BATCH_DRAW_SVG_MAX_BYTES + 1)
    with (
        patch.object(tasks, "authorize", return_value=_ACCOUNT),
        patch.object(tasks, "check_key_limit", return_value=None),
        patch.object(tasks, "MultiDeviceCoordinator") as mock_coord,
        patch.object(tasks, "connect", return_value=MagicMock()) as mock_connect,
    ):
        response = tasks_client.post(
            "/device/v1/app/devices/batch-draw",
            json={"device_ids": ["d-1"], "svg": huge_svg, "coordinator_id": "c-1"},
            headers=_AUTH,
        )
    assert response.status_code == 413
    mock_coord.assert_not_called()
    mock_connect.assert_not_called()  # rejected before device access checks


def test_batch_draw_within_limit_passes_size_check(tasks_client):
    """A normal-size SVG passes both new guards and reaches the coordinator."""
    coordinator = MagicMock()

    async def fake_execute(_svg, _ids, _cid):
        return {"status": "ok"}

    coordinator.execute_coordinated = fake_execute
    with (
        patch.object(tasks, "authorize", return_value=_ACCOUNT),
        patch.object(tasks, "check_key_limit", return_value=None),
        patch.object(tasks, "require_device_control", return_value=None),
        patch.object(tasks, "connect") as mock_connect,
        patch.object(tasks, "MultiDeviceCoordinator", return_value=coordinator),
    ):
        mock_connect.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        response = tasks_client.post(
            "/device/v1/app/devices/batch-draw",
            json={"device_ids": ["d-1"], "svg": "<svg></svg>", "coordinator_id": "c-1"},
            headers=_AUTH,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
