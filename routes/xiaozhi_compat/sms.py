"""Mock SMS verification helpers shared by native and compatibility routes."""

from __future__ import annotations

import os
import secrets

from fastapi.responses import JSONResponse

from .http_helpers import err

SMS_EXPIRES_SECONDS = 300


def configured_login_code() -> str:
    return os.environ.get("LIMA_XIAOZHI_LOGIN_CODE", "").strip()


def login_code_error() -> JSONResponse | None:
    if configured_login_code():
        return None
    return err(503, "SMS verification code is not configured", 503)


def validate_login_code(code: str) -> bool:
    expected = configured_login_code()
    return bool(expected and code and secrets.compare_digest(code, expected))


def sms_verification_payload(phone: str) -> dict[str, object]:
    return {"phone": phone, "mock": True, "expiresIn": SMS_EXPIRES_SECONDS}
