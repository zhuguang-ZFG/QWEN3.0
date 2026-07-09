"""Tests for /v1/images/generations and /device/v1/app/images/generations."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_app_images
from routes import images as img
from routes import images_cache as image_cache


def _fake_xmiaom(url: str = "https://example.com/fake.png", backend: str = "xmiaom"):
    async def _xmiaom(prompt: str, size: str):
        return [{"url": url, "backend": backend}]

    return _xmiaom


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("XMIAOM_API_KEY", "test-xmiaom-key")
    img._record_request_fn = None
    image_cache.clear_cache()


@pytest.fixture
def public_client(monkeypatch):
    monkeypatch.setattr(img, "_generate_via_xmiaom", _fake_xmiaom())
    app = FastAPI()
    app.include_router(img.router)
    return TestClient(app)


@pytest.fixture
def device_app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "images_device_app.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setattr(img, "_generate_via_xmiaom", _fake_xmiaom())

    from device_app_helpers import seed_account_and_device
    from dlc_api.device_app_router import register_device_app_routes

    seed_account_and_device(device_id="d-img", device_sn="SN-IMG-01")

    app = FastAPI()
    register_device_app_routes(app)
    return TestClient(app)


def _auth_header(account_id: str = "a-owner") -> dict[str, str]:
    import time

    import jwt

    now = int(time.time())
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": "user",
        "iat": now,
        "exp": now + 3600,
    }
    token = jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


class TestPublicImageGenerations:
    def test_image_generations_success(self, public_client):
        response = public_client.post(
            "/v1/images/generations",
            headers={"Authorization": "Bearer test-key"},
            json={"prompt": "a cat", "size": "1024x1024", "n": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["data"][0]["url"] == "https://example.com/fake.png"
        assert "created" in data

    def test_image_generations_rejects_missing_auth(self, public_client):
        response = public_client.post(
            "/v1/images/generations",
            json={"prompt": "a cat", "size": "1024x1024"},
        )
        assert response.status_code == 401

    def test_image_generations_rejects_invalid_auth(self, public_client):
        response = public_client.post(
            "/v1/images/generations",
            headers={"Authorization": "Bearer wrong-key"},
            json={"prompt": "a cat", "size": "1024x1024"},
        )
        assert response.status_code == 401

    def test_image_generations_validation_error(self, public_client):
        response = public_client.post(
            "/v1/images/generations",
            headers={"Authorization": "Bearer test-key"},
            json={"prompt": "a cat", "size": "9999x9999"},
        )
        assert response.status_code == 400
        assert "error" in response.json()

    def test_image_generations_empty_prompt(self, public_client):
        response = public_client.post(
            "/v1/images/generations",
            headers={"Authorization": "Bearer test-key"},
            json={"prompt": "   ", "size": "1024x1024"},
        )
        assert response.status_code == 400

    def test_image_cache_returns_same_url(self, public_client, monkeypatch):
        call_count = {"n": 0}

        async def counting_xmiaom(prompt: str, size: str):
            call_count["n"] += 1
            return [{"url": f"https://example.com/img{call_count['n']}.png", "backend": "xmiaom"}]

        monkeypatch.setattr(img, "_generate_via_xmiaom", counting_xmiaom)

        response1 = public_client.post(
            "/v1/images/generations",
            headers={"Authorization": "Bearer test-key"},
            json={"prompt": "cache me", "size": "1024x1024"},
        )
        assert response1.status_code == 200
        url1 = response1.json()["data"][0]["url"]

        response2 = public_client.post(
            "/v1/images/generations",
            headers={"Authorization": "Bearer test-key"},
            json={"prompt": "cache me", "size": "1024x1024"},
        )
        assert response2.status_code == 200
        url2 = response2.json()["data"][0]["url"]

        assert url1 == url2
        assert call_count["n"] == 1


class TestDeviceAppImageGenerations:
    def test_device_app_image_generations_success(self, device_app_client):
        response = device_app_client.post(
            "/device/v1/app/images/generations",
            headers=_auth_header(),
            json={"prompt": "a robot", "size": "1024x1024"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["data"][0]["url"] == "https://example.com/fake.png"
        assert data["backend"] == device_app_images.PUBLIC_IMAGE_BACKEND_LABEL

    def test_device_app_image_generations_rejects_missing_auth(self, device_app_client):
        response = device_app_client.post(
            "/device/v1/app/images/generations",
            json={"prompt": "a robot", "size": "1024x1024"},
        )
        assert response.status_code == 401

    def test_device_app_image_generations_rejects_invalid_auth(self, device_app_client):
        response = device_app_client.post(
            "/device/v1/app/images/generations",
            headers={"Authorization": "Bearer invalid-token"},
            json={"prompt": "a robot", "size": "1024x1024"},
        )
        assert response.status_code == 401

    def test_device_app_image_generations_empty_prompt(self, device_app_client):
        response = device_app_client.post(
            "/device/v1/app/images/generations",
            headers=_auth_header(),
            json={"prompt": "   ", "size": "1024x1024"},
        )
        assert response.status_code == 400

    def test_device_app_image_generations_rate_limited(self, device_app_client, monkeypatch):
        import rate_limiter
        from config import settings

        rate_limiter.reset()
        monkeypatch.setattr(settings.DEVICE, "dlc_image_per_min", 1)
        payload = {"prompt": "a robot", "size": "1024x1024"}
        first = device_app_client.post(
            "/device/v1/app/images/generations",
            headers=_auth_header(),
            json=payload,
        )
        assert first.status_code == 200, first.text
        second = device_app_client.post(
            "/device/v1/app/images/generations",
            headers=_auth_header(),
            json=payload,
        )
        assert second.status_code == 429


def test_server_dlc_exposes_v1_images_generations(monkeypatch):
    """server_dlc.app 暴露 /v1/images/generations（P4/P5 误删后恢复）。"""
    monkeypatch.setattr(img, "_generate_via_xmiaom", _fake_xmiaom())
    import server_dlc

    paths = {r.path for r in server_dlc.app.routes}
    assert "/v1/images/generations" in paths
