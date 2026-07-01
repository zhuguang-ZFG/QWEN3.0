"""routes/images backend fallback and image-to-image tests."""

from __future__ import annotations

from routes import images as img
from routes import images_backends as backends
from routes import images_cache as image_cache
from .conftest import auth_header


class _FakeFreeTheAIResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


class _FakeFreeTheAIClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        return self._response


def _patch_freetheai_client(monkeypatch, payload):
    class _Client(_FakeFreeTheAIClient):
        _response = _FakeFreeTheAIResponse(payload)

    monkeypatch.setattr(backends.httpx, "AsyncClient", _Client)


def _patch_xmiaom_empty(monkeypatch):
    async def fake_xmiaom(prompt: str, size: str):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)


def test_freetheai_fallback_when_xmiaom_fails(client, monkeypatch):
    image_cache.clear_cache()
    _patch_xmiaom_empty(monkeypatch)
    monkeypatch.setattr(backends.backend_config, "FREETHEAI_API_KEY", "fta-test-key")
    _patch_freetheai_client(monkeypatch, {"data": [{"url": "https://example.com/freetheai.png"}]})

    response = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://example.com/freetheai.png"


def test_freetheai_b64_json_becomes_data_uri(client, monkeypatch):
    image_cache.clear_cache()
    _patch_xmiaom_empty(monkeypatch)
    monkeypatch.setattr(backends.backend_config, "FREETHEAI_API_KEY", "fta-test-key")
    _patch_freetheai_client(monkeypatch, {"data": [{"b64_json": "aGVsbG8="}]})

    response = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"].startswith("data:image/png;base64,")


def test_no_freetheai_key_falls_back_to_pollinations(client, monkeypatch):
    image_cache.clear_cache()
    _patch_xmiaom_empty(monkeypatch)
    monkeypatch.setattr(backends.backend_config, "FREETHEAI_API_KEY", "")

    response = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert "image.pollinations.ai" in response.json()["data"][0]["url"]


def test_image_url_triggers_i2i_backend(client, monkeypatch):
    image_cache.clear_cache()
    i2i_called = {"n": 0}

    async def fake_i2i(prompt: str, image_url: str, size: str, n: int) -> list[dict]:
        i2i_called["n"] += 1
        assert image_url == "https://example.com/input.jpg"
        return [{"url": "https://example.com/i2i.png", "backend": "dashscope_i2i"}]

    monkeypatch.setattr(img, "_generate_via_dashscope_i2i", fake_i2i)

    response = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={
            "prompt": "stylize this",
            "image_url": "https://example.com/input.jpg",
            "size": "1024x1024",
            "n": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://example.com/i2i.png"
    assert i2i_called["n"] == 1


def test_image_url_i2i_failure_falls_back_to_text_to_image(client, monkeypatch):
    image_cache.clear_cache()

    async def fake_i2i(prompt: str, image_url: str, size: str, n: int) -> list[dict]:
        return []

    monkeypatch.setattr(img, "_generate_via_dashscope_i2i", fake_i2i)

    response = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={
            "prompt": "stylize this",
            "image_url": "https://example.com/input.jpg",
            "size": "1024x1024",
            "n": 1,
        },
    )
    assert response.status_code == 200
    assert "image.pollinations.ai" in response.json()["data"][0]["url"]
