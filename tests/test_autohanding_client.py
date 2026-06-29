"""Tests for integrations/autohanding/client.py."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from integrations.autohanding import client


@pytest.fixture(autouse=True)
def _reset_shared_client():
    """Each test gets a fresh shared client slot to avoid cross-test cache."""
    original = client._SHARED_ASYNC_CLIENT
    client._SHARED_ASYNC_CLIENT = None
    yield
    client._SHARED_ASYNC_CLIENT = original


def _zip_with_png(png_bytes: bytes = b"fake-png") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("page_1.png", png_bytes)
    return buf.getvalue()


def _make_client(response: httpx.Response | Exception) -> MagicMock:
    """Build a mock AsyncClient usable by the shared-client path."""
    mock_client = MagicMock()
    if isinstance(response, Exception):
        mock_client.post = AsyncMock(side_effect=response)
    else:
        mock_client.post = AsyncMock(return_value=response)
    mock_client.aclose = AsyncMock()
    return mock_client


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
    mock_client = _make_client(response)

    client._SHARED_ASYNC_CLIENT = mock_client
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
    mock_client = _make_client(response)

    client._SHARED_ASYNC_CLIENT = mock_client
    with pytest.raises(client.AutohandingRateLimitError):
        await client.convert_text("hello")


@pytest.mark.asyncio
async def test_convert_text_plain_text_rate_limit():
    response = _mock_response(
        status_code=200,
        content="请求频率过高，请稍后".encode("utf-8"),
        text="请求频率过高，请稍后",
    )
    mock_client = _make_client(response)

    client._SHARED_ASYNC_CLIENT = mock_client
    with pytest.raises(client.AutohandingRateLimitError):
        await client.convert_text("hello")


@pytest.mark.asyncio
async def test_convert_text_timeout():
    mock_client = _make_client(httpx.TimeoutException("timeout"))

    client._SHARED_ASYNC_CLIENT = mock_client
    with pytest.raises(client.AutohandingClientError, match="request timeout"):
        await client.convert_text("hello", max_retries=0)


@pytest.mark.asyncio
async def test_convert_text_retries_then_succeeds():
    zip_bytes = _zip_with_png(b"png-data")
    success_response = _mock_response(content=zip_bytes, headers={"content-type": "application/zip"})
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=[httpx.TimeoutException("timeout"), success_response])
    mock_client.aclose = AsyncMock()

    client._SHARED_ASYNC_CLIENT = mock_client
    with patch("asyncio.sleep"):
        result = await client.convert_text("hello", max_retries=1)

    assert result == b"png-data"
    assert mock_client.post.await_count == 2


@pytest.mark.asyncio
async def test_convert_text_rate_limit_not_retried():
    response = _mock_response(status_code=429)
    mock_client = _make_client(response)

    client._SHARED_ASYNC_CLIENT = mock_client
    with patch("asyncio.sleep"):
        with pytest.raises(client.AutohandingRateLimitError):
            await client.convert_text("hello", max_retries=2)

    assert mock_client.post.await_count == 1


@pytest.mark.asyncio
async def test_convert_text_missing_png_in_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", b"no png")
    response = _mock_response(content=buf.getvalue(), headers={"content-type": "application/zip"})
    mock_client = _make_client(response)

    client._SHARED_ASYNC_CLIENT = mock_client
    with pytest.raises(client.AutohandingClientError, match="no PNG found"):
        await client.convert_text("hello", max_retries=0)


@pytest.mark.asyncio
async def test_close_autohanding_client():
    mock_client = _make_client(_mock_response())
    client._SHARED_ASYNC_CLIENT = mock_client

    await client.close_autohanding_client()

    assert client._SHARED_ASYNC_CLIENT is None
    mock_client.aclose.assert_awaited_once()
