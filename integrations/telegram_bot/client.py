"""Async Telegram Bot API client for image storage.

Used by the device app gallery to avoid storing images on the LiMa server.
Only file IDs and metadata are kept locally; actual image bytes live on
Telegram's servers.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .constants import DEFAULT_API_BASE, DEFAULT_TIMEOUT_SECONDS, MAX_FILE_SIZE_BYTES

_log = logging.getLogger(__name__)


class TelegramBotError(Exception):
    """Raised when the Telegram Bot API returns an error."""

    def __init__(self, message: str, telegram_code: int | None = None) -> None:
        super().__init__(message)
        self.telegram_code = telegram_code


class TelegramNotConfiguredError(Exception):
    """Raised when TELEGRAM_BOT_TOKEN is missing or empty."""


class TelegramFileTooLargeError(Exception):
    """Raised when an image exceeds Telegram's file size limit."""


def _env(key: str, default: str = "") -> str:
    import os

    return os.environ.get(key, default)


def get_configured() -> bool:
    """Return True if a Telegram bot token is present."""
    return bool(_env("TELEGRAM_BOT_TOKEN"))


def _require_token() -> str:
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise TelegramNotConfiguredError("TELEGRAM_BOT_TOKEN is not set")
    return token


def _require_chat_id() -> str:
    chat_id = _env("TELEGRAM_GALLERY_CHAT_ID")
    if not chat_id:
        raise TelegramNotConfiguredError("TELEGRAM_GALLERY_CHAT_ID is not set")
    return chat_id


def _api_base() -> str:
    return _env("TELEGRAM_API_BASE", DEFAULT_API_BASE)


def _api_url(token: str, method: str) -> str:
    return f"{_api_base()}/bot{token}/{method}"


def _check_response(payload: dict[str, Any]) -> Any:
    """Extract the result from a Telegram response or raise TelegramBotError."""
    if payload.get("ok"):
        return payload.get("result")
    error_code = payload.get("error_code")
    description = payload.get("description", "unknown Telegram error")
    raise TelegramBotError(f"Telegram API error {error_code}: {description}", telegram_code=error_code)


async def send_photo(
    image_bytes: bytes,
    filename: str,
    caption: str | None = None,
) -> str:
    """Upload an image to Telegram and return its persistent file_id.

    For a personal material library the user creates a private channel/group,
    adds the bot, and sets TELEGRAM_GALLERY_CHAT_ID.
    """
    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        raise TelegramFileTooLargeError(
            f"image size {len(image_bytes)} exceeds Telegram limit {MAX_FILE_SIZE_BYTES}"
        )

    token = _require_token()
    chat_id = _require_chat_id()

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        response = await client.post(
            _api_url(token, "sendPhoto"),
            data={"chat_id": chat_id, "caption": caption or ""},
            files={"photo": (filename, image_bytes, "image/jpeg")},
        )
    response.raise_for_status()
    result = _check_response(response.json())
    # result contains a PhotoSize array; the largest is last.
    photos = result.get("photo", [])
    if not photos:
        raise TelegramBotError("Telegram did not return photo metadata")
    return str(photos[-1].get("file_id", ""))


async def get_file_url(file_id: str) -> str:
    """Return a temporary HTTPS URL for downloading a Telegram file.

    The URL is valid for at least several minutes but is not persistent;
    callers should not store it long-term.
    """
    token = _require_token()
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        response = await client.post(_api_url(token, "getFile"), json={"file_id": file_id})
    response.raise_for_status()
    result = _check_response(response.json())
    file_path = result.get("file_path", "")
    if not file_path:
        raise TelegramBotError("Telegram did not return file_path")
    return f"{_api_base()}/file/bot{token}/{file_path}"


async def download_file(file_path_or_url: str) -> bytes:
    """Download a Telegram file by its file_path or a full get_file_url result."""
    token = _require_token()
    # If a full URL was passed, use it; otherwise build it from file_path.
    if file_path_or_url.startswith("https://"):
        url = file_path_or_url
    else:
        url = f"{_api_base()}/file/bot{token}/{file_path_or_url}"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS, trust_env=False) as client:
        response = await client.get(url)
    response.raise_for_status()
    return response.content


class TelegramBotClient:
    """Stateful wrapper around the module-level functions."""

    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = token or _env("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or _env("TELEGRAM_GALLERY_CHAT_ID")
        if not self.token:
            raise TelegramNotConfiguredError("TelegramBotClient requires a token")
        if not self.chat_id:
            raise TelegramNotConfiguredError("TelegramBotClient requires a chat_id")

    async def send_photo(self, image_bytes: bytes, filename: str, caption: str | None = None) -> str:
        if len(image_bytes) > MAX_FILE_SIZE_BYTES:
            raise TelegramFileTooLargeError(
                f"image size {len(image_bytes)} exceeds Telegram limit {MAX_FILE_SIZE_BYTES}"
            )
        url = _api_url(self.token, "sendPhoto")
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS, trust_env=False) as client:
            response = await client.post(
                url,
                data={"chat_id": self.chat_id, "caption": caption or ""},
                files={"photo": (filename, image_bytes, "image/jpeg")},
            )
        response.raise_for_status()
        result = _check_response(response.json())
        photos = result.get("photo", [])
        if not photos:
            raise TelegramBotError("Telegram did not return photo metadata")
        return str(photos[-1].get("file_id", ""))

    async def get_file_url(self, file_id: str) -> str:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS, trust_env=False) as client:
            response = await client.post(
                _api_url(self.token, "getFile"), json={"file_id": file_id}
            )
        response.raise_for_status()
        result = _check_response(response.json())
        file_path = result.get("file_path", "")
        if not file_path:
            raise TelegramBotError("Telegram did not return file_path")
        return f"{_api_base()}/file/bot{self.token}/{file_path}"

    async def download_file(self, file_path_or_url: str) -> bytes:
        if file_path_or_url.startswith("https://"):
            url = file_path_or_url
        else:
            url = f"{_api_base()}/file/bot{self.token}/{file_path_or_url}"
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response.content
