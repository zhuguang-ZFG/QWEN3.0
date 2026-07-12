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


# SEC-04: draw_from_image enforces a host allowlist (api.telegram.org) plus a
# DNS-resolution SSRF guard. Stub the resolver at its real home
# (device_gateway.image_url_validation) so image tests don't depend on ambient
# DNS — patching dlc_api.routes._resolve_hostname never worked after the
# validation moved out of routes.py.
@pytest.fixture(autouse=True)
def _stub_image_dns(monkeypatch):
    monkeypatch.setattr(
        "device_gateway.image_url_validation._resolve_hostname",
        lambda host: ["149.154.167.220"],  # public Telegram IP
    )


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
