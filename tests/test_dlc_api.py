"""Tests for dlc_api P1 routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import rate_limiter
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

# SEC-04: draw_from_image now enforces a host allowlist (api.telegram.org) plus
# DNS-resolution SSRF guard. Stub the resolver so image tests exercise the happy
# path without real network lookups.
import dlc_api.routes as _dlc_routes  # noqa: E402

_dlc_routes._resolve_hostname = lambda host: ["149.154.167.220"]  # public Telegram IP


def test_health_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "dlc-drawing"


@patch("dlc_api.routes.handle_write", new_callable=AsyncMock)
def test_preview_write_text(mock_write) -> None:
    mock_write.return_value = {
        "status": "success",
        "path_data": [{"x": 0, "y": 0}],
        "preview_svg": "<svg></svg>",
        "width": 100,
        "height": 50,
        "model": "deterministic",
        "error": None,
    }

    client = TestClient(app)
    response = client.post(
        "/dlc/tasks/preview",
        json={"type": "write_text", "device_id": "dev-1", "payload": {"text": "你好"}},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["model"] == "deterministic"
    mock_write.assert_awaited_once_with("你好")


@patch("dlc_api.routes.handle_draw", new_callable=AsyncMock)
def test_dispatch_draw_generated(mock_draw) -> None:
    mock_draw.return_value = {
        "status": "success",
        "svg_path": "M0,0",
        "preview_svg": "<svg></svg>",
        "width": 180,
        "height": 180,
        "model": "preset:circle",
        "error": None,
    }

    with patch("dlc_api.routes.dispatch_task", new_callable=AsyncMock) as mock_dispatch:
        mock_dispatch.return_value = {
            "status": "queued",
            "task_id": "task-draw-1",
            "queue_depth": 1,
            "error": None,
        }
        client = TestClient(app)
        response = client.post(
            "/dlc/tasks/dispatch",
            json={
                "type": "draw_generated",
                "device_id": "dev-1",
                "payload": {"prompt": "画一个圆"},
                "request_id": "req-1",
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["task_id"] == "task-draw-1"
        mock_draw.assert_awaited_once_with("画一个圆", device_id="dev-1", allow_dashscope=False)
        mock_dispatch.assert_awaited_once()


def test_legacy_write_endpoint_removed() -> None:
    client = TestClient(app)
    response = client.post("/write", json={"device_id": "dev-1", "text": "你好"})
    assert response.status_code == 404


def test_legacy_draw_endpoint_removed() -> None:
    client = TestClient(app)
    response = client.post("/draw", json={"device_id": "dev-1", "prompt": "圆"})
    assert response.status_code == 404


@patch("dlc_api.routes.handle_draw_from_image", new_callable=AsyncMock)
def test_preview_draw_from_image(mock_draw_from_image) -> None:
    mock_draw_from_image.return_value = {
        "status": "success",
        "svg_path": "M0,0",
        "preview_svg": "<svg></svg>",
        "width": 180,
        "height": 180,
        "model": "provided_image",
        "error": None,
    }
    client = TestClient(app)
    response = client.post(
        "/dlc/tasks/preview",
        json={
            "type": "draw_from_image",
            "device_id": "dev-1",
            "payload": {"image_url": "https://api.telegram.org/file/bot123/img.png"},
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["svg_path"] == "M0,0"
    assert data["preview_svg"] == "<svg></svg>"
    assert data["model"] == "provided_image"
    mock_draw_from_image.assert_awaited_once_with("https://api.telegram.org/file/bot123/img.png", device_id="dev-1")


def test_preview_draw_from_image_missing_url() -> None:
    client = TestClient(app)
    response = client.post(
        "/dlc/tasks/preview",
        json={"type": "draw_from_image", "device_id": "dev-1", "payload": {}},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert "image_url" in data["error"].lower()


@patch("dlc_api.routes.handle_draw_from_image", new_callable=AsyncMock)
def test_dispatch_draw_from_image(mock_draw_from_image) -> None:
    mock_draw_from_image.return_value = {
        "status": "success",
        "svg_path": "M0,0",
        "preview_svg": "<svg></svg>",
        "width": 180,
        "height": 180,
        "model": "provided_image",
        "error": None,
    }
    with patch("dlc_api.routes.dispatch_task", new_callable=AsyncMock) as mock_dispatch:
        mock_dispatch.return_value = {
            "status": "queued",
            "task_id": "task-img-1",
            "queue_depth": 1,
            "error": None,
        }
        client = TestClient(app)
        response = client.post(
            "/dlc/tasks/dispatch",
            json={
                "type": "draw_from_image",
                "device_id": "dev-1",
                "payload": {"image_url": "https://api.telegram.org/file/bot123/img.png"},
                "request_id": "req-2",
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["task_id"] == "task-img-1"
        mock_draw_from_image.assert_awaited_once_with("https://api.telegram.org/file/bot123/img.png", device_id="dev-1")
        motion_task = mock_dispatch.call_args[0][1]
        assert motion_task["entrypoint"] == "draw_from_image"
        assert motion_task["source"] == "dlc_api"
        assert motion_task["request_id"] == "req-2"


@patch("dlc_api.routes.handle_draw_from_image", new_callable=AsyncMock)
def test_dispatch_draw_from_image_failed(mock_draw_from_image) -> None:
    mock_draw_from_image.return_value = {
        "status": "failed",
        "svg_path": "",
        "preview_svg": "",
        "width": 0,
        "height": 0,
        "model": "provided_image",
        "error": "conversion failed",
    }
    client = TestClient(app)
    response = client.post(
        "/dlc/tasks/dispatch",
        json={
            "type": "draw_from_image",
            "device_id": "dev-1",
            "payload": {"image_url": "https://api.telegram.org/file/bot123/bad.png"},
            "request_id": "req-3",
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["error"] == "conversion failed"


@patch("dlc_api.routes.get_device_status", new_callable=AsyncMock)
def test_get_device_status_success(mock_get_device_status) -> None:
    mock_get_device_status.return_value = {
        "device_id": "dev-1",
        "online": True,
        "working": True,
        "active_task_id": "task-001",
        "firmware_version": "u8-3.9.0",
        "last_seen_at": "2026-07-04T09:01:00Z",
        "shadow": {"last_motion_event": {"phase": "running"}},
    }
    client = TestClient(app)
    response = client.get(
        "/dlc/devices/dev-1/status",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "device_id": "dev-1",
        "online": True,
        "working": True,
        "active_task_id": "task-001",
        "firmware_version": "u8-3.9.0",
        "last_seen_at": "2026-07-04T09:01:00Z",
        "shadow": {"last_motion_event": {"phase": "running"}},
    }
    mock_get_device_status.assert_awaited_once_with("dev-1")


def test_get_device_status_rejects_device_mismatch() -> None:
    client = TestClient(app)
    response = client.get(
        "/dlc/devices/dev-2/status",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "device_id mismatch"


def test_validate_path_valid() -> None:
    """POST /dlc/tasks/validate with a valid path returns ok=True."""
    client = TestClient(app)
    response = client.post(
        "/dlc/tasks/validate",
        json={"path": [{"x": 10, "y": 20}, {"x": 50, "y": 60}]},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["errors"] == []


def test_validate_path_out_of_bounds() -> None:
    """POST /dlc/tasks/validate with out-of-bounds points returns errors."""
    client = TestClient(app)
    response = client.post(
        "/dlc/tasks/validate",
        json={"path": [{"x": 999, "y": 0}]},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert len(data["errors"]) > 0
