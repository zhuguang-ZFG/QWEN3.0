"""Tests for integrations.telegram_bot.client."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import httpx
import pytest

from integrations.telegram_bot.client import (
    TelegramBotClient,
    TelegramBotError,
    TelegramFileTooLargeError,
    TelegramNotConfiguredError,
    download_file,
    get_configured,
    get_file_url,
    send_photo,
)
from integrations.telegram_bot.constants import MAX_FILE_SIZE_BYTES


@pytest.fixture(autouse=True)
def _clear_telegram_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure TELEGRAM_BOT_TOKEN is unset unless a test explicitly sets it."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_GALLERY_CHAT_ID", raising=False)


def test_get_configured_false() -> None:
    assert get_configured() is False


def test_get_configured_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    assert get_configured() is True


async def test_send_photo_without_token_raises() -> None:
    with pytest.raises(TelegramNotConfiguredError):
        await send_photo(b"x", "test.jpg")


async def test_send_photo_file_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_GALLERY_CHAT_ID", "456")
    with pytest.raises(TelegramFileTooLargeError):
        await send_photo(b"x" * (MAX_FILE_SIZE_BYTES + 1), "test.jpg")


async def test_send_photo_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_GALLERY_CHAT_ID", "456")

    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ok": True,
        "result": {
            "photo": [
                {"file_id": "small", "width": 90},
                {"file_id": "large", "width": 1024},
            ]
        },
    }
    mock_response.raise_for_status.return_value = None

    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object):
            return False

        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            captured["url"] = url
            captured["data"] = kwargs.get("data")
            captured["files"] = kwargs.get("files")
            return mock_response

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    file_id = await send_photo(b"image", "test.jpg", caption="hello")
    assert file_id == "large"
    assert captured["url"] == "https://api.telegram.org/bot123:abc/sendPhoto"
    data = captured["data"]
    assert data["chat_id"] == "456"
    assert data["caption"] == "hello"


async def test_send_photo_telegram_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_GALLERY_CHAT_ID", "456")

    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 400
    mock_response.json.return_value = {"ok": False, "error_code": 400, "description": "Bad Request"}
    mock_response.raise_for_status.return_value = None

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object):
            return False

        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            return mock_response

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    with pytest.raises(TelegramBotError) as exc_info:
        await send_photo(b"image", "test.jpg")
    assert exc_info.value.telegram_code == 400


async def test_get_file_url_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")

    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ok": True,
        "result": {"file_id": "abc", "file_path": "photos/file.jpg"},
    }
    mock_response.raise_for_status.return_value = None

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object):
            return False

        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            return mock_response

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    url = await get_file_url("abc")
    assert url == "https://api.telegram.org/file/bot123:abc/photos/file.jpg"


async def test_download_file_by_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")

    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.content = b"downloaded"
    mock_response.raise_for_status.return_value = None

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object):
            return False

        async def get(self, url: str) -> httpx.Response:
            return mock_response

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    data = await download_file("https://api.telegram.org/file/bot123:abc/photos/file.jpg")
    assert data == b"downloaded"


async def test_client_class_requires_token_and_chat() -> None:
    with pytest.raises(TelegramNotConfiguredError):
        TelegramBotClient(token=None, chat_id=None)

    with pytest.raises(TelegramNotConfiguredError):
        TelegramBotClient(token="123", chat_id=None)


def test_client_class_accepts_explicit_values() -> None:
    client = TelegramBotClient(token="123:abc", chat_id="456")
    assert client.token == "123:abc"
    assert client.chat_id == "456"


async def test_client_send_photo_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ok": True,
        "result": {"photo": [{"file_id": "the-file-id"}]},
    }
    mock_response.raise_for_status.return_value = None

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object):
            return False

        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            return mock_response

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    client = TelegramBotClient(token="123:abc", chat_id="456")
    file_id = await client.send_photo(b"image", "test.jpg")
    assert file_id == "the-file-id"
