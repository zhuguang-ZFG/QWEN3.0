"""SEC-04: draw_from_image SSRF hardening — DNS resolution + host allowlist.

Current ``_validate_image_url`` only blocks literal private/loopback IPs and
``localhost``. Two gaps remain:

1. A public hostname that resolves to a private IP (DNS rebinding) passes
   the literal check undetected — e.g. ``attacker.com`` → ``10.0.0.5``.
2. Any HTTPS host is accepted; the design spec (§13.1 SEC-04) mandates a
   host allowlist of only ``api.telegram.org`` (the gallery image source).

These tests are RED until the hardening is implemented.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import rate_limiter
from dlc_api.app import app
from dlc_api.deps import verify_dlc_api_token


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Isolate the module-level sliding-window state so repeated dev-1 calls
    across cases in this file do not exhaust the per-minute quota (S3)."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def _override_token() -> str:
    return "dev-1"


app.dependency_overrides[verify_dlc_api_token] = _override_token


def _preview_request(image_url: str) -> dict:
    return {
        "type": "draw_from_image",
        "device_id": "dev-1",
        "payload": {"image_url": image_url},
    }


def _post(client: TestClient, image_url: str):
    return client.post(
        "/dlc/tasks/preview",
        json=_preview_request(image_url),
        headers={"Authorization": "Bearer test-token"},
    )


# ── RED: non-allowlisted host must be rejected (host whitelist) ────────────────


def test_reject_non_telegram_host():
    """HTTPS to an arbitrary public host (example.com) must be rejected."""
    client = TestClient(app)
    response = _post(client, "https://example.com/img.png")
    data = response.json()
    assert data["status"] == "failed"
    assert "not allowed" in data["error"].lower() or "blocked" in data["error"].lower()


def test_reject_localhost():
    """localhost is still blocked even though it is public-ish."""
    client = TestClient(app)
    response = _post(client, "https://localhost:8000/img.png")
    data = response.json()
    assert data["status"] == "failed"


# ── RED: literal private IPs still blocked (regression) ───────────────────────


def test_reject_literal_private_ip():
    client = TestClient(app)
    for bad_url in [
        "https://10.0.0.1/img.png",
        "https://192.168.1.1/img.png",
        "https://127.0.0.1/img.png",
        "https://169.254.169.254/latest/meta-data/",
    ]:
        response = _post(client, bad_url)
        data = response.json()
        assert data["status"] == "failed", f"{bad_url} should be blocked"
        err = data["error"].lower()
        assert "blocked" in err or "private" in err


# ── RED: DNS rebinding — public hostname that resolves to private IP ──────────


def test_reject_dns_rebind_to_private_ip(monkeypatch):
    """An allowlisted host whose A record resolves to 10.x must still be rejected.

    Uses api.telegram.org (passes the host allowlist) but forces DNS to return a
    private IP, exercising the rebinding guard rather than the allowlist check.
    Patches ``dlc_api.routes._resolve_hostname`` (the DNS-resolution helper).
    """
    from device_gateway import image_url_validation as iv

    monkeypatch.setattr(iv, "_resolve_hostname", lambda host: ["10.66.6.6"])

    client = TestClient(app)
    response = _post(client, "https://api.telegram.org/file/bot123/img.png")
    data = response.json()
    assert data["status"] == "failed"
    assert "blocked" in data["error"].lower() or "private" in data["error"].lower()


# ── RED: allowlisted host (api.telegram.org) passes when resolve is public ────


def test_allow_telegram_host(monkeypatch):
    """api.telegram.org must pass both the whitelist and the DNS resolution."""
    from device_gateway import image_url_validation as iv

    monkeypatch.setattr(iv, "_resolve_hostname", lambda host: ["149.154.167.220"])  # public Telegram IP
    with patch("dlc_api.routes.handle_draw_from_image", new_callable=AsyncMock) as mock:
        mock.return_value = {
            "status": "success",
            "svg_path": "M0,0",
            "preview_svg": "<svg></svg>",
            "width": 100,
            "height": 100,
            "model": "telegram_img",
            "error": None,
        }
        client = TestClient(app)
        response = _post(client, "https://api.telegram.org/file/bot123/img.png")
        data = response.json()
        assert data["status"] == "success", f"telegram host should be allowed; got: {data}"


# ── images/generations i2i path must use the same SSRF guard ─────────────────


def test_images_generations_i2i_rejects_private_image_url(monkeypatch):
    """/_generate_image_urls must validate image_url before DashScope i2i."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient as TC

    from routes import images as img

    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    called = {"n": 0}

    async def spy_i2i(prompt: str, image_url: str, size: str, n: int):
        called["n"] += 1
        return [{"url": "https://example.com/x.png"}]

    async def fake_xmiaom(prompt: str, size: str):
        return [{"url": "https://example.com/x.png"}]

    monkeypatch.setattr(img, "_generate_via_dashscope_i2i", spy_i2i)
    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    app_local = FastAPI()
    app_local.include_router(img.router)
    client = TC(app_local)
    response = client.post(
        "/v1/images/generations",
        headers={"Authorization": "Bearer test-key"},
        json={"prompt": "x", "image_url": "https://192.168.1.1/a.png"},
    )
    assert response.status_code == 400
    assert called["n"] == 0
