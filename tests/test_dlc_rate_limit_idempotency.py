"""S3 rate limiting + S10 idempotency for dlc_api dispatch/preview.

S3: /dlc/tasks/preview and /dlc/tasks/dispatch must be rate-limited per caller
    device, with draw_from_image getting a lower quota (higher CPU/cost).
S10: /dlc/tasks/dispatch must dedupe replays via an Idempotency-Key header so a
    repeated Bearer request cannot dispatch the same motion command twice.

RED until the guards are implemented.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from dlc_api.app import app
from dlc_api.deps import verify_dlc_api_token
from dlc_api import routes as _dlc_routes

# Telegram host resolves public so SSRF guard passes in image tests.
_dlc_routes._resolve_hostname = lambda host: ["149.154.167.220"]


def _override_token() -> str:
    return "dev-1"


app.dependency_overrides[verify_dlc_api_token] = _override_token


def _write_body() -> dict:
    return {"type": "write_text", "device_id": "dev-1", "payload": {"text": "你好"}}


# ── S3: rate limiting ─────────────────────────────────────────────────────────


def test_preview_rate_limited_returns_429() -> None:
    """When the shared limiter rejects the key, preview returns HTTP 429."""
    with patch("dlc_api.routes.check_key_limit") as mock_limit:
        from fastapi.responses import JSONResponse

        mock_limit.return_value = JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit exceeded. Try again later.", "type": "rate_limit_error"}},
        )
        client = TestClient(app)
        response = client.post(
            "/dlc/tasks/preview",
            json=_write_body(),
            headers={"Authorization": "Bearer test-token"},
        )
    assert response.status_code == 429
    assert response.json()["error"]["type"] == "rate_limit_error"


def test_dispatch_rate_limited_returns_429() -> None:
    with patch("dlc_api.routes.check_key_limit") as mock_limit:
        from fastapi.responses import JSONResponse

        mock_limit.return_value = JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit exceeded. Try again later.", "type": "rate_limit_error"}},
        )
        client = TestClient(app)
        response = client.post(
            "/dlc/tasks/dispatch",
            json=_write_body(),
            headers={"Authorization": "Bearer test-token"},
        )
    assert response.status_code == 429


@patch("dlc_api.routes.handle_write", new_callable=AsyncMock)
def test_preview_not_limited_passes(mock_write) -> None:
    """When the limiter allows the key (returns None), the request proceeds."""
    mock_write.return_value = {
        "status": "success",
        "path_data": [{"x": 0, "y": 0}],
        "preview_svg": "<svg></svg>",
        "width": 10,
        "height": 10,
        "model": "deterministic",
        "error": None,
    }
    with patch("dlc_api.routes.check_key_limit", return_value=None):
        client = TestClient(app)
        response = client.post(
            "/dlc/tasks/preview",
            json=_write_body(),
            headers={"Authorization": "Bearer test-token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_draw_from_image_uses_lower_quota() -> None:
    """draw_from_image must call check_key_limit with a smaller default_max than write_text."""
    calls: list[int] = []

    def _record(key, default_max, *, window=60.0):
        calls.append(default_max)
        return None

    with patch("dlc_api.routes.check_key_limit", side_effect=_record):
        with patch("dlc_api.routes.handle_write", new_callable=AsyncMock) as mw:
            mw.return_value = {"status": "success", "model": "x", "error": None}
            client = TestClient(app)
            client.post(
                "/dlc/tasks/preview",
                json=_write_body(),
                headers={"Authorization": "Bearer t"},
            )
        with patch("dlc_api.routes.handle_draw_from_image", new_callable=AsyncMock) as mi:
            mi.return_value = {
                "status": "success",
                "svg_path": "M0,0",
                "width": 1,
                "height": 1,
                "model": "x",
                "error": None,
            }
            client.post(
                "/dlc/tasks/preview",
                json={
                    "type": "draw_from_image",
                    "device_id": "dev-1",
                    "payload": {"image_url": "https://api.telegram.org/file/bot1/x.png"},
                },
                headers={"Authorization": "Bearer t"},
            )
    write_quota, image_quota = calls[0], calls[1]
    assert image_quota < write_quota, f"draw_from_image quota ({image_quota}) must be < write quota ({write_quota})"


# ── S10: idempotency ──────────────────────────────────────────────────────────


@patch("dlc_api.routes.handle_write", new_callable=AsyncMock)
def test_dispatch_idempotency_dedupes_replay(mock_write) -> None:
    """Same Idempotency-Key twice → the underlying dispatch runs only once."""
    mock_write.return_value = {
        "status": "success",
        "svg_path": "M0,0",
        "preview_svg": "<svg></svg>",
        "width": 10,
        "height": 10,
        "model": "deterministic",
        "error": None,
    }

    seen: set[str] = set()

    def _claim(idem_key: str, task_id: str, *, ttl: int = 600) -> bool:
        if idem_key in seen:
            return False
        seen.add(idem_key)
        return True

    with patch("dlc_api.routes.check_key_limit", return_value=None):
        with patch("dlc_api.routes._claim_idempotency_key", side_effect=_claim):
            with patch("dlc_api.routes.dispatch_task", new_callable=AsyncMock) as mock_dispatch:
                mock_dispatch.return_value = {"status": "queued", "task_id": "task-1", "queue_depth": 1, "error": None}
                client = TestClient(app)
                headers = {"Authorization": "Bearer t", "Idempotency-Key": "abc-123"}
                first = client.post("/dlc/tasks/dispatch", json=_write_body(), headers=headers)
                second = client.post("/dlc/tasks/dispatch", json=_write_body(), headers=headers)

    assert first.status_code == 200
    assert first.json()["status"] == "queued"
    # Second call is a replay: underlying dispatch must NOT run again.
    assert mock_dispatch.await_count == 1
    assert second.json()["status"] in {"duplicate", "queued"}


@patch("dlc_api.routes.handle_write", new_callable=AsyncMock)
def test_dispatch_without_idempotency_key_still_works(mock_write) -> None:
    """No Idempotency-Key header → dispatch proceeds normally (backward compat)."""
    mock_write.return_value = {
        "status": "success",
        "svg_path": "M0,0",
        "width": 10,
        "height": 10,
        "model": "deterministic",
        "error": None,
    }
    with patch("dlc_api.routes.check_key_limit", return_value=None):
        with patch("dlc_api.routes.dispatch_task", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = {"status": "queued", "task_id": "task-2", "queue_depth": 1, "error": None}
            client = TestClient(app)
            response = client.post(
                "/dlc/tasks/dispatch",
                json=_write_body(),
                headers={"Authorization": "Bearer t"},
            )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert mock_dispatch.await_count == 1
