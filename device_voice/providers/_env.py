"""Shared environment variable helpers for voice providers."""

from __future__ import annotations

import os


def _get_env_with_aliases(*aliases: str) -> str:
    """Return the first non-empty environment variable value."""
    for name in aliases:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _get_dashscope_api_key() -> str:
    """Return DashScope API key from explicit var or ALIYUN_API_KEY fallback."""
    return _get_env_with_aliases("DASHSCOPE_API_KEY", "ALIYUN_API_KEY")
