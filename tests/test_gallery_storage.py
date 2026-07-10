"""Tests for device_gateway.gallery_storage."""

from __future__ import annotations

import pytest

from device_gateway.gallery_storage import TelegramGalleryBackend, get_gallery_backend
from integrations.telegram_bot.client import TelegramNotConfiguredError


def test_get_gallery_backend_defaults_to_telegram(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_GALLERY_CHAT_ID", "456")
    monkeypatch.delenv("GALLERY_STORAGE_BACKEND", raising=False)
    backend = get_gallery_backend()
    assert isinstance(backend, TelegramGalleryBackend)


def test_get_gallery_backend_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GALLERY_STORAGE_BACKEND", "s3")
    with pytest.raises(TelegramNotConfiguredError, match="unsupported"):
        get_gallery_backend()
