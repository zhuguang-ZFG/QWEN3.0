"""Tests for lima_sdk Python client."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from lima_sdk import AsyncLiMaClient, LiMaClient, LiMaAPIError

API_KEY = "sk-test"
BASE_URL = "https://chat.example.com"


def _json_response(data: dict[str, Any], status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _mock_transport(handlers: dict[tuple[str, str], dict[str, Any] | httpx.Response]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, str(request.url))
        matched = handlers.get(key)
        if matched is None:
            return httpx.Response(404, text=f"no mock for {key}")
        if isinstance(matched, httpx.Response):
            return matched
        return _json_response(matched)

    return httpx.MockTransport(handler)


def test_chat_completion() -> None:
    expected = {
        "id": "chat-1",
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": "hello"}}],
    }
    transport = _mock_transport({("POST", f"{BASE_URL}/v1/chat/completions"): expected})
    client = LiMaClient(API_KEY, base_url=BASE_URL, transport=transport)
    resp = client.chat.create(model="lima-1.3", messages=[{"role": "user", "content": "hi"}])
    assert resp["choices"][0]["message"]["content"] == "hello"


def test_chat_completion_stream() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"hi"}}]}\n',
        'data: {"choices":[{"delta":{"content":"!"}}]}\n',
        "data: [DONE]\n",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(200, text="".join(lines), headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    client = LiMaClient(API_KEY, base_url=BASE_URL, transport=transport)
    stream = client.chat.create(model="lima-1.3", messages=[{"role": "user", "content": "hi"}], stream=True)
    chunks = list(stream)
    assert len(chunks) == 2
    assert chunks[0]["choices"][0]["delta"]["content"] == "hi"


def test_images_generate() -> None:
    expected = {"data": [{"url": "https://example.com/img.png"}]}
    transport = _mock_transport({("POST", f"{BASE_URL}/v1/images/generations"): expected})
    client = LiMaClient(API_KEY, base_url=BASE_URL, transport=transport)
    resp = client.images.generate(model="dall-e-3", prompt="a cat")
    assert resp["data"][0]["url"] == "https://example.com/img.png"


def test_devices_list_and_status() -> None:
    transport = _mock_transport(
        {
            ("GET", f"{BASE_URL}/device/v1/app/devices"): {"devices": [{"deviceId": "d1"}]},
            ("GET", f"{BASE_URL}/device/v1/app/devices/d1/status"): {"online": True},
        }
    )
    client = LiMaClient(API_KEY, base_url=BASE_URL, transport=transport)
    assert client.devices.list()["devices"][0]["deviceId"] == "d1"
    assert client.devices.status("d1")["online"] is True


def test_devices_create_and_get_task() -> None:
    transport = _mock_transport(
        {
            ("POST", f"{BASE_URL}/device/v1/app/devices/d1/tasks"): {"taskId": "t1"},
            ("GET", f"{BASE_URL}/device/v1/app/tasks/t1"): {"taskId": "t1", "status": "running"},
        }
    )
    client = LiMaClient(API_KEY, base_url=BASE_URL, transport=transport)
    assert client.devices.create_task("d1", text="hello")["taskId"] == "t1"
    assert client.devices.get_task("t1")["status"] == "running"


def test_assets_list_and_create() -> None:
    transport = _mock_transport(
        {
            ("GET", f"{BASE_URL}/device/v1/app/assets"): {"assets": [{"assetId": "a1"}]},
            ("POST", f"{BASE_URL}/device/v1/app/assets"): {"assetId": "a2"},
        }
    )
    client = LiMaClient(API_KEY, base_url=BASE_URL, transport=transport)
    assert client.assets.list()["assets"][0]["assetId"] == "a1"
    assert client.assets.create(title="cat", category="svg", content="<svg/>")["assetId"] == "a2"


def test_api_error() -> None:
    transport = _mock_transport(
        {
            ("GET", f"{BASE_URL}/device/v1/app/devices/d1"): httpx.Response(
                404,
                json={"error": {"message": "not found", "type": "not_found"}},
            )
        }
    )
    client = LiMaClient(API_KEY, base_url=BASE_URL, transport=transport)
    with pytest.raises(LiMaAPIError) as exc_info:
        client.devices.get("d1")
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.message


@pytest.mark.anyio
async def test_async_chat() -> None:
    expected = {
        "id": "chat-2",
        "choices": [{"message": {"role": "assistant", "content": "async hello"}}],
    }
    transport = _mock_transport({("POST", f"{BASE_URL}/v1/chat/completions"): expected})
    async with AsyncLiMaClient(API_KEY, base_url=BASE_URL, transport=transport) as client:
        resp = await client.chat.create(model="lima-1.3", messages=[{"role": "user", "content": "hi"}])
    assert resp["choices"][0]["message"]["content"] == "async hello"


@pytest.mark.anyio
async def test_async_devices() -> None:
    transport = _mock_transport({("GET", f"{BASE_URL}/device/v1/app/devices"): {"devices": [{"deviceId": "d2"}]}})
    async with AsyncLiMaClient(API_KEY, base_url=BASE_URL, transport=transport) as client:
        devices = await client.devices.list()
    assert devices["devices"][0]["deviceId"] == "d2"
