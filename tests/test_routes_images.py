"""Tests for routes/images.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import images as img
from routes import images_cache as image_cache


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    img._record_request_fn = None
    image_cache.clear_cache()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(img.router)
    return TestClient(app)


def _auth_header():
    return {"Authorization": "Bearer test-key"}


def test_missing_auth_returns_401(client):
    response = client.post("/v1/images/generations", json={"prompt": "hi"})
    assert response.status_code == 401


def test_invalid_body_returns_400(client):
    response = client.post("/v1/images/generations", headers=_auth_header(), json={"prompt": ""})
    assert response.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"prompt": "hi", "size": "abc"},
        {"prompt": "hi", "size": "3000x3000"},
        {"prompt": "hi", "n": 0},
        {"prompt": "hi", "n": 20},
    ],
)
def test_validation_errors(client, body):
    response = client.post("/v1/images/generations", headers=_auth_header(), json=body)
    assert response.status_code == 400


def test_empty_prompt_returns_400(client):
    response = client.post("/v1/images/generations", headers=_auth_header(), json={"prompt": "   "})
    assert response.status_code == 400


def test_successful_generation(client):
    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 2},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    assert "image.pollinations.ai" in data[0]["url"]
    assert "width=1024" in data[0]["url"]


def test_chinese_prompt_gets_prefixed(client):
    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "小猫"},
    )
    assert response.status_code == 200
    url = response.json()["data"][0]["url"]
    assert "high%20quality%2C%20detailed%2C" in url


def test_record_request_callback(client):
    recorder = MagicMock()
    img.inject_record_request(recorder)
    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a dog"},
    )
    assert response.status_code == 200
    recorder.assert_called_once()
    assert recorder.call_args.args[0] == "a dog"
    assert recorder.call_args.args[2] == "image_generation"


def test_build_pollinations_url():
    url = img.build_pollinations_url("hello world", "512x256")
    assert url.startswith("https://image.pollinations.ai/prompt/")
    assert "width=512" in url
    assert "height=256" in url
    assert "nologo=true" in url


def test_cache_returns_same_result_without_second_backend_call(client, monkeypatch):
    image_cache.clear_cache()
    call_count = {"n": 0}

    async def fake_xmiaom(prompt: str, size: str):
        call_count["n"] += 1
        return [{"url": "https://example.com/cached.png", "backend": "xmiaom"}]

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)

    response1 = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "cache me", "size": "1024x1024"},
    )
    assert response1.status_code == 200
    url1 = response1.json()["data"][0]["url"]

    response2 = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "cache me", "size": "1024x1024"},
    )
    assert response2.status_code == 200
    url2 = response2.json()["data"][0]["url"]

    assert url1 == url2
    assert call_count["n"] == 1


def test_skip_cache_header_bypasses_cache(client, monkeypatch):
    image_cache.clear_cache()
    call_count = {"n": 0}

    async def fake_xmiaom(prompt: str, size: str):
        call_count["n"] += 1
        return [{"url": f"https://example.com/img{call_count['n']}.png", "backend": "xmiaom"}]

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)

    response1 = client.post(
        "/v1/images/generations",
        headers={**_auth_header(), "X-Skip-Cache": "1"},
        json={"prompt": "skip me", "size": "1024x1024"},
    )
    assert response1.status_code == 200
    url1 = response1.json()["data"][0]["url"]

    response2 = client.post(
        "/v1/images/generations",
        headers={**_auth_header(), "X-Skip-Cache": "1"},
        json={"prompt": "skip me", "size": "1024x1024"},
    )
    assert response2.status_code == 200
    url2 = response2.json()["data"][0]["url"]

    assert url1 != url2
    assert call_count["n"] == 2


def test_freetheai_fallback_when_xmiaom_fails(client, monkeypatch):
    image_cache.clear_cache()

    async def fake_xmiaom(prompt: str, size: str):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    monkeypatch.setattr(img.backend_config, "FREETHEAI_API_KEY", "fta-test-key")

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"data": [{"url": "https://example.com/freetheai.png"}]}

        def raise_for_status(self):
            pass

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr(img.httpx, "AsyncClient", _FakeClient)

    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://example.com/freetheai.png"


def test_freetheai_b64_json_becomes_data_uri(client, monkeypatch):
    image_cache.clear_cache()

    async def fake_xmiaom(prompt: str, size: str):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    monkeypatch.setattr(img.backend_config, "FREETHEAI_API_KEY", "fta-test-key")

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"data": [{"b64_json": "aGVsbG8="}]}

        def raise_for_status(self):
            pass

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr(img.httpx, "AsyncClient", _FakeClient)

    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"].startswith("data:image/png;base64,")


def test_no_freetheai_key_falls_back_to_pollinations(client, monkeypatch):
    image_cache.clear_cache()

    async def fake_xmiaom(prompt: str, size: str):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    monkeypatch.setattr(img.backend_config, "FREETHEAI_API_KEY", "")

    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert "image.pollinations.ai" in response.json()["data"][0]["url"]
