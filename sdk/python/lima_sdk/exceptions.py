"""SDK exceptions."""

from __future__ import annotations

from typing import Any


class LiMaSDKError(Exception):
    """Base SDK error."""


class LiMaAPIError(LiMaSDKError):
    """Raised when the LiMa API returns a non-2xx response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.response_body = response_body or {}
