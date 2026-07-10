"""Gallery object-storage backends (P2: swappable Telegram / future S3-R2)."""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from integrations.telegram_bot.client import TelegramBotClient, TelegramNotConfiguredError


@runtime_checkable
class GalleryStorageBackend(Protocol):
    """Persist image bytes and resolve download URLs by opaque file id."""

    async def send_photo(self, image_bytes: bytes, filename: str, caption: str | None = None) -> str: ...

    async def get_file_url(self, file_id: str) -> str: ...

    async def download_file(self, file_path_or_url: str) -> bytes: ...


class TelegramGalleryBackend:
    """Telegram Bot API storage (current production backend)."""

    def __init__(self, client: TelegramBotClient | None = None) -> None:
        self._client = client or TelegramBotClient()

    async def send_photo(self, image_bytes: bytes, filename: str, caption: str | None = None) -> str:
        return await self._client.send_photo(image_bytes, filename, caption=caption)

    async def get_file_url(self, file_id: str) -> str:
        return await self._client.get_file_url(file_id)

    async def download_file(self, file_path_or_url: str) -> bytes:
        return await self._client.download_file(file_path_or_url)


def get_gallery_backend() -> GalleryStorageBackend:
    """Return the configured gallery storage backend."""
    backend = (os.environ.get("GALLERY_STORAGE_BACKEND") or "telegram").strip().lower()
    if backend == "telegram":
        return TelegramGalleryBackend()
    raise TelegramNotConfiguredError(f"unsupported GALLERY_STORAGE_BACKEND: {backend}")
