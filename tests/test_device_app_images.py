"""Tests for /device/v1/app/images/generations."""

from __future__ import annotations

import pytest

from device_app_helpers import client as make_client, headers, seed_account_and_device, seed_binding


@pytest.fixture
def image_client(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device(device_id="d-image", device_sn="SN-IMAGE-01")
    seed_binding(device_id="d-image", account_id="a-owner", binding_id="b-image")
    return client


def test_image_generation_requires_auth(image_client):
    response = image_client.post("/device/v1/app/images/generations", json={"prompt": "a cat"})
    assert response.status_code == 401


def test_image_generation_rejects_empty_prompt(image_client):
    response = image_client.post(
        "/device/v1/app/images/generations",
        json={"prompt": "  "},
        headers=headers("a-owner"),
    )
    assert response.status_code == 400


def test_image_generation_rejects_invalid_size(image_client):
    response = image_client.post(
        "/device/v1/app/images/generations",
        json={"prompt": "a cat", "size": "invalid"},
        headers=headers("a-owner"),
    )
    assert response.status_code == 400


def test_image_generation_returns_urls(image_client, monkeypatch):
    from routes import device_app_images as app_images_mod

    async def _fake_generate(prompt: str, size: str, n: int, options: dict, *, skip_cache: bool = False):
        return [{"url": "https://example.com/img.png", "backend": "xmiaom"}], "xmiaom", 100

    monkeypatch.setattr(app_images_mod, "_generate_image_urls", _fake_generate)

    response = image_client.post(
        "/device/v1/app/images/generations",
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
        headers=headers("a-owner"),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == [{"url": "https://example.com/img.png"}]
    assert data["backend"] == "xmiaom"
    assert "created" in data
