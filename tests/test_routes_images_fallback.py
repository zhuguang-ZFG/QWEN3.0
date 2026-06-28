"""新增生图后端降级测试（Agnes / SiliconFlow / 智谱 CogView）。

从 test_routes_images.py 拆出（保持单文件 ≤300 行约束）。
验证 images.py 六后端降级链路：xmiaom → agnes → siliconflow → zhipu → freetheai → pollinations。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import images as img
from routes import images_backends as backends
from routes import images_cache as image_cache
from routes import images_pollinations as pollinations


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    img._record_request_fn = None
    image_cache.clear_cache()
    pollinations._PROMPT_TRANSLATE_ENABLED = False


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(img.router)
    return TestClient(app)


def _auth_header():
    return {"Authorization": "Bearer test-key"}


class _FakeResponse:
    status_code = 200

    def json(self):
        return {"data": [{"url": "https://example.com/generated.png"}]}

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


def test_agnes_fallback_when_xmiaom_fails(client, monkeypatch):
    """xmiaom 失败 → agnes 成功（agnes 在降级链中排在 siliconflow/zhipu/freetheai/pollinations 之前）。"""
    image_cache.clear_cache()

    async def fake_xmiaom(prompt: str, size: str):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    monkeypatch.setattr(backends.backend_config, "AGNES_AI_API_KEY", "agnes-test-key")
    monkeypatch.setattr(backends.httpx, "AsyncClient", _FakeClient)

    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://example.com/generated.png"


def test_siliconflow_fallback_when_xmiaom_and_agnes_fail(client, monkeypatch):
    """xmiaom + agnes 都失败 → siliconflow 成功。"""
    image_cache.clear_cache()

    async def fake_xmiaom(prompt: str, size: str):
        return []

    async def fake_agnes(prompt: str, size: str, n: int):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    monkeypatch.setattr(img, "_generate_via_agnes", fake_agnes)
    monkeypatch.setattr(backends.backend_config, "SILICONFLOW_API_KEY", "sf-test-key")
    monkeypatch.setattr(backends.httpx, "AsyncClient", _FakeClient)

    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://example.com/generated.png"


def test_zhipu_fallback_when_others_fail(client, monkeypatch):
    """xmiaom + agnes + siliconflow 都失败 → 智谱 cogview 成功。"""
    image_cache.clear_cache()

    async def fake_xmiaom(prompt: str, size: str):
        return []

    async def fake_empty(prompt: str, size: str, n: int):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    monkeypatch.setattr(img, "_generate_via_agnes", fake_empty)
    monkeypatch.setattr(img, "_generate_via_siliconflow", fake_empty)
    monkeypatch.setattr(backends.backend_config, "ZHIPU_API_KEY", "zhipu-test-key")
    monkeypatch.setattr(backends.httpx, "AsyncClient", _FakeClient)

    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://example.com/generated.png"


def test_baidu_fallback_when_others_fail(client, monkeypatch):
    """xmiaom + agnes + siliconflow + zhipu 都失败 → 百度千帆 SD-XL 成功。"""
    image_cache.clear_cache()

    async def fake_xmiaom(prompt: str, size: str):
        return []

    async def fake_empty(prompt: str, size: str, n: int):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    monkeypatch.setattr(img, "_generate_via_agnes", fake_empty)
    monkeypatch.setattr(img, "_generate_via_siliconflow", fake_empty)
    monkeypatch.setattr(img, "_generate_via_zhipu", fake_empty)
    monkeypatch.setattr(backends.backend_config, "BAIDU_API_KEY", "baidu-test-key")
    monkeypatch.setattr(backends.httpx, "AsyncClient", _FakeClient)

    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://example.com/generated.png"


def test_tencent_fallback_when_others_fail(client, monkeypatch):
    """前 5 个后端都失败 → 腾讯混元生图成功。"""
    image_cache.clear_cache()

    async def fake_xmiaom(prompt: str, size: str):
        return []

    async def fake_empty(prompt: str, size: str, n: int):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    monkeypatch.setattr(img, "_generate_via_agnes", fake_empty)
    monkeypatch.setattr(img, "_generate_via_siliconflow", fake_empty)
    monkeypatch.setattr(img, "_generate_via_zhipu", fake_empty)
    monkeypatch.setattr(img, "_generate_via_baidu", fake_empty)
    monkeypatch.setattr(backends.backend_config, "TENCENT_API_KEY", "tencent-test-key")
    monkeypatch.setattr(backends.httpx, "AsyncClient", _FakeClient)

    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://example.com/generated.png"


def test_volcengine_fallback_when_others_fail(client, monkeypatch):
    """前 6 个后端都失败 → 字节豆包 Seedream 成功。"""
    image_cache.clear_cache()

    async def fake_xmiaom(prompt: str, size: str):
        return []

    async def fake_empty(prompt: str, size: str, n: int):
        return []

    monkeypatch.setattr(img, "_generate_via_xmiaom", fake_xmiaom)
    monkeypatch.setattr(img, "_generate_via_agnes", fake_empty)
    monkeypatch.setattr(img, "_generate_via_siliconflow", fake_empty)
    monkeypatch.setattr(img, "_generate_via_zhipu", fake_empty)
    monkeypatch.setattr(img, "_generate_via_baidu", fake_empty)
    monkeypatch.setattr(img, "_generate_via_tencent", fake_empty)
    monkeypatch.setattr(backends.backend_config, "VOLCENGINE_API_KEY", "volc-test-key")
    monkeypatch.setattr(backends.httpx, "AsyncClient", _FakeClient)

    response = client.post(
        "/v1/images/generations",
        headers=_auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 1},
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://example.com/generated.png"
