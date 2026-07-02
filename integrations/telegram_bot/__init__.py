"""Telegram Bot integration for LiMa gallery storage.

DEPRECATED (notification channel retired 2026-06): Only gallery image storage
remains active. See client.py for details.
"""

from .client import (
    TelegramBotClient,
    download_file,
    get_configured,
    get_file_url,
    send_photo,
)
from .constants import MAX_FILE_SIZE_BYTES

__all__ = [
    "TelegramBotClient",
    "download_file",
    "get_configured",
    "get_file_url",
    "send_photo",
    "MAX_FILE_SIZE_BYTES",
]
