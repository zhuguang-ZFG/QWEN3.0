"""Tests for integrations/autohanding/client.py."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from integrations.autohanding import client


def _zip_with_png(png_bytes: bytes = b"fake-png") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("page_1.png", png_bytes)
    return buf.getvalue()


def _make_async_client(response: httpx.Response) -> MagicMock:
    client_mock = MagicMock()
    client_mock.post = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _mock_response(
    status_code: int = 200,
    content: bytes = b"",
    headers: dict[str, str] | None = None,
    text: str = "",
) -> httpx.Response:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.content = content
    response.headers = headers or {}
    response.text = text
    return response


@pytest.mark.asyncio
async def test_convert_text_success():
    zip_bytes = _zip_with_png(b"png-data")
    response = _mock_response(content=zip_bytes, headers={"content-type": "application/zip"})
    cm = _make_async_client(response)

    with patch("httpx.AsyncClient") as AsyncClientMock:
        AsyncClientMock.return_value = cm
        result = await client.convert_text("hello world")

    assert result == b"png-data"


@pytest.mark.asyncio
async def test_convert_text_empty_text_raises():
    with pytest.raises(client.AutohandingClientError, match="empty text"):
        await client.convert_text("   ")


@pytest.mark.asyncio
async def test_convert_text_too_long_raises():
    with pytest.raises(client.AutohandingClientError, match="text too long"):
        await client.convert_text("x" * (client.constants.MAX_TEXT_LENGTH + 1))


@pytest.mark.asyncio
async def test_convert_text_rate_limit_status():
    response = _mock_response(status_code=429)
    cm = _make_async_client(response)

    with patch("httpx.AsyncClient") as AsyncClientMock:
        AsyncClientMock.return_value = cm
        with pytest.raises(client.AutohandingRateLimitError):
            await client.convert_text("hello")


@pytest.mark.asyncio
async def test_convert_text_plain_text_rate_limit():
    response = _mock_response(
        status_code=200,
        content="请求频率过高，请稍后".encode("utf-8"),
        text="请求频率过高，请稍后",
    )
    cm = _make_async_client(response)

    with patch("httpx.AsyncClient") as AsyncClientMock:
        AsyncClientMock.return_value = cm
        with pytest.raises(client.AutohandingRateLimitError):
            await client.convert_text("hello")


@pytest.mark.asyncio
async def test_convert_text_timeout():
    client_mock = MagicMock()
    client_mock.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client_mock)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient") as AsyncClientMock:
        AsyncClientMock.return_value = cm
        with pytest.raises(client.AutohandingClientError, match="request timeout"):
            await client.convert_text("hello")


@pytest.mark.asyncio
async def test_convert_text_missing_png_in_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", b"no png")
    response = _mock_response(content=buf.getvalue(), headers={"content-type": "application/zip"})
    cm = _make_async_client(response)

    with patch("httpx.AsyncClient") as AsyncClientMock:
        AsyncClientMock.return_value = cm
        with pytest.raises(client.AutohandingClientError, match="no PNG found"):
            await client.convert_text("hello")
