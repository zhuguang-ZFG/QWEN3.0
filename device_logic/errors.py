"""Shared device-app business errors (HTTP layers map to responses)."""

from __future__ import annotations


class DeviceLogicError(Exception):
    def __init__(self, code: int, message: str, http_status: int = 400) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)
