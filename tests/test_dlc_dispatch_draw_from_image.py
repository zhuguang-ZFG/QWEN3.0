"""Integration test: dispatch draw_from_image must send run_path, not write_text.

Verifies the HIGH-1 fix: _build_dispatch_payload constructs a pre-parsed
voice_task so the downstream NL intent path is bypassed.  The dispatched
task must carry run_path capability with the already-generated path, not
fall back to write_text{"text":"描图"}.

Does NOT mock dispatch_task (dlc_api.routes.dispatch_task) — the real
dispatch_task extracts voice_task from the motion_task and passes it into
create_and_route_task.  Only create_and_route_task is mocked at the
dlc_core.dispatch level to capture the DeviceTaskRequest and verify
its voice_task field.
"""

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
    """Isolate per-test rate-limit state so quota does not bleed across cases."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def _override_token() -> str:
    return "dev-1"


app.dependency_overrides[verify_dlc_api_token] = _override_token


@pytest.fixture(autouse=True)
def _stub_image_dns(monkeypatch):
    """Stub DNS resolution so image URL validation does not depend on ambient DNS."""
    monkeypatch.setattr(
        "device_gateway.image_url_validation._resolve_hostname",
        lambda host: ["149.154.167.220"],  # public Telegram IP
    )


def _assert_run_path_voice_task(req: DeviceTaskRequest) -> None:
    """Verify DeviceTaskRequest carries a run_path voice_task with path."""
    assert req.voice_task is not None, "voice_task must be set"
    vt = req.voice_task
    assert vt["capability"] == "run_path", f"expected run_path, got {vt['capability']}"
    assert isinstance(vt.get("params"), dict) and "path" in vt["params"], "params must contain path"
    assert len(vt["params"]["path"]) > 0, "path must have motion points"
    assert vt.get("source") == "dlc_api"
    assert vt.get("entrypoint") == "draw_from_image"
    assert vt["capability"] != "write_text", "BUG REGRESSION: dispatch must NOT fall back to write_text"
    assert req.text == "描图"


@patch("dlc_core.dispatch.active_tasks_for_device", return_value=[])
@patch("dlc_api.motion_payload.handle_draw_from_image", new_callable=AsyncMock)
@patch("dlc_core.dispatch.create_and_route_task", new_callable=AsyncMock)
def test_dispatch_draw_from_image_sends_run_path(
    mock_create_route: AsyncMock,
    mock_draw_from_image: AsyncMock,
    mock_active: list,
) -> None:
    """Verify draw_from_image dispatch builds voice_task with run_path + path."""
    mock_draw_from_image.return_value = {
        "status": "success",
        "svg_path": "M10,20 L30,40 L50,60",
        "preview_svg": "<svg><path d='M10,20'/></svg>",
        "width": 180,
        "height": 180,
        "model": "provided_image",
        "error": None,
    }
    mock_create_route.return_value = DeviceTaskRouteResult(
        status="queued_no_delivery",
        sent=False,
        queue_depth=1,
        task={"capability": "run_path", "task_id": "task-1"},
    )
    response = TestClient(app).post(
        "/dlc/tasks/dispatch",
        json={
            "type": "draw_from_image",
            "device_id": "dev-1",
            "payload": {"image_url": "https://api.telegram.org/file/bot123/img.png"},
            "request_id": "req-draw-img-1",
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "queued_no_delivery"
    mock_create_route.assert_awaited_once()
    assert mock_create_route.await_args is not None
    _assert_run_path_voice_task(mock_create_route.await_args.args[0])


@patch("dlc_api.motion_payload.handle_draw_from_image", new_callable=AsyncMock)
def test_dispatch_draw_from_image_fallback_on_failure(
    mock_draw_from_image: AsyncMock,
) -> None:
    """When handle_draw_from_image fails, dispatch returns failed (not queued)."""
    mock_draw_from_image.return_value = {
        "status": "failed",
        "svg_path": "",
        "preview_svg": "",
        "width": 0,
        "height": 0,
        "model": "disabled",
        "error": "mock image error",
    }

    client = TestClient(app)
    response = client.post(
        "/dlc/tasks/dispatch",
        json={
            "type": "draw_from_image",
            "device_id": "dev-1",
            "payload": {"image_url": "https://api.telegram.org/file/bot123/img.png"},
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    # _build_dispatch_payload returns failed status, so dispatch_task is never
    # called and the response is "failed" (not queued).
    assert data["status"] == "failed"
    assert "error" in data
