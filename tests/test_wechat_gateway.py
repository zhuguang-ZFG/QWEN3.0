"""Tests for device_logic.wechat_gateway."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from device_logic.wechat_gateway import WechatLoginError, WechatMiniappGateway


class FakeResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict[str, Any]:
        return self._json


class FakeAsyncClient:
    """Stub httpx.AsyncClient for jscode2session tests."""

    def __init__(self, response: FakeResponse) -> None:
        self._response = response

    async def get(self, *args: Any, **kwargs: Any) -> FakeResponse:
        return self._response

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, response: FakeResponse) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(response))


@pytest.mark.asyncio
async def test_jscode2session_returns_openid(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse({"openid": "o123", "session_key": "sk", "unionid": "u456"})
    _patch_async_client(monkeypatch, response)
    gateway = WechatMiniappGateway("appid", "secret")
    result = await gateway.jscode2session("abc")
    assert result["openid"] == "o123"
    assert result["session_key"] == "sk"
    assert result["unionid"] == "u456"


@pytest.mark.asyncio
async def test_jscode2session_raises_on_wechat_error(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse({"errcode": 40029, "errmsg": "invalid code"})
    _patch_async_client(monkeypatch, response)
    gateway = WechatMiniappGateway("appid", "secret")
    with pytest.raises(WechatLoginError, match="invalid code"):
        await gateway.jscode2session("bad")


@pytest.mark.asyncio
async def test_jscode2session_raises_when_missing_openid(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse({"session_key": "sk"})
    _patch_async_client(monkeypatch, response)
    gateway = WechatMiniappGateway("appid", "secret")
    with pytest.raises(WechatLoginError, match="missing openid"):
        await gateway.jscode2session("abc")


@pytest.mark.asyncio
async def test_jscode2session_raises_when_not_configured() -> None:
    gateway = WechatMiniappGateway("", "")
    with pytest.raises(WechatLoginError, match="not configured"):
        await gateway.jscode2session("abc")
