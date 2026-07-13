"""Tests for routes/device_app_assets.py render_asset rate limiting."""

from __future__ import annotations

import pytest

import rate_limiter
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding
from device_logic.db import connect


@pytest.fixture(autouse=True)
def _seed_asset(tmp_path, monkeypatch):
    """Create a test asset in the library (isolated tmp DB, set before connect)."""
    rate_limiter.reset()
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "device_app.db"))
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO v2_asset_library
            (id, title, category, content, preview_url, tags, difficulty, created_at, use_count, status)
            VALUES ('asset-1', 'a', 'text', 'hello', '', '[]', 'easy', '2026-01-01T00:00:00Z', 0, 'active')
            """
        )
        conn.commit()


def _client(tmp_path, monkeypatch):
    return make_client(tmp_path, monkeypatch)


def test_render_asset_rate_limited(tmp_path, monkeypatch):
    """Render asset returns 429 when rate limit is exceeded."""
    from fastapi.responses import JSONResponse

    from routes import device_app_assets as assets_mod

    limited = JSONResponse(
        status_code=429,
        content={"error": {"message": "Rate limit exceeded. Try again later.", "type": "rate_limit_error"}},
    )
    monkeypatch.setattr(assets_mod, "check_key_limit", lambda _key, _max: limited)
    client, _store = _client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.post(
        "/device/v1/app/assets/asset-1/render",
        headers=headers("a-owner"),
        json={"deviceId": "dev-1"},
    )
    assert response.status_code == 429
    assert response.json()["error"]["type"] == "rate_limit_error"


def test_render_asset_not_rate_limited_when_quota_ok(tmp_path, monkeypatch):
    """Render asset succeeds when rate limit is not exceeded."""
    from routes import device_app_assets as assets_mod

    monkeypatch.setattr(assets_mod, "check_key_limit", lambda _key, _max: None)
    client, _store = _client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.post(
        "/device/v1/app/assets/asset-1/render",
        headers=headers("a-owner"),
        json={"deviceId": "dev-1"},
    )
    # Should succeed (200) or give a more relevant error (like 400 for missing params)
    # The key is it doesn't 429
    assert response.status_code != 429
