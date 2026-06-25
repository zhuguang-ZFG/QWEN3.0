"""LiMa Python SDK.

A minimal, httpx-based client for LiMa's OpenAI-compatible chat/image endpoints
and the native device-app API.
"""

from __future__ import annotations

from lima_sdk.client import AsyncLiMaClient, LiMaClient
from lima_sdk.exceptions import LiMaAPIError, LiMaSDKError

__all__ = ["LiMaClient", "AsyncLiMaClient", "LiMaSDKError", "LiMaAPIError"]
__version__ = "0.1.0"
