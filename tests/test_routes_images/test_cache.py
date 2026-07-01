"""routes/images cache-related tests."""

from __future__ import annotations

from routes import images as img
from routes import images_cache as image_cache
from conftest import auth_header


def test_cache_returns_same_result_without_second_backend_call(client, monkeypatch):
    image_cache.clear_cache()
    call_count = {"n": 0}

    async def fake_xmiaom(prompt: str, size: str):
        call_count["n"] += 1
        return [{"url": "https://example.com/cached.png", "backend": "xmiaom"}]

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)

    response1 = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "cache me", "size": "1024x1024"},
    )
    assert response1.status_code == 200
    url1 = response1.json()["data"][0]["url"]

    response2 = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "cache me", "size": "1024x1024"},
    )
    assert response2.status_code == 200
    url2 = response2.json()["data"][0]["url"]

    assert url1 == url2
    assert call_count["n"] == 1


def test_cache_key_includes_n_and_options(client, monkeypatch):
    image_cache.clear_cache()
    call_count = {"n": 0}

    async def fake_xmiaom(prompt: str, size: str):
        call_count["n"] += 1
        return [{"url": f"https://example.com/img{call_count['n']}.png", "backend": "xmiaom"}]

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)

    response1 = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "key test", "size": "1024x1024", "n": 1},
    )
    assert response1.status_code == 200

    response2 = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "key test", "size": "1024x1024", "n": 2},
    )
    assert response2.status_code == 200

    response3 = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "key test", "size": "1024x1024", "n": 2, "seed": 123},
    )
    assert response3.status_code == 200

    assert call_count["n"] == 3


def test_skip_cache_header_bypasses_cache(client, monkeypatch):
    image_cache.clear_cache()
    call_count = {"n": 0}

    async def fake_xmiaom(prompt: str, size: str):
        call_count["n"] += 1
        return [{"url": f"https://example.com/img{call_count['n']}.png", "backend": "xmiaom"}]

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)

    response1 = client.post(
        "/v1/images/generations",
        headers={**auth_header(), "X-Skip-Cache": "1"},
        json={"prompt": "skip me", "size": "1024x1024"},
    )
    assert response1.status_code == 200
    url1 = response1.json()["data"][0]["url"]

    response2 = client.post(
        "/v1/images/generations",
        headers={**auth_header(), "X-Skip-Cache": "1"},
        json={"prompt": "skip me", "size": "1024x1024"},
    )
    assert response2.status_code == 200
    url2 = response2.json()["data"][0]["url"]

    assert url1 != url2
    assert call_count["n"] == 2
