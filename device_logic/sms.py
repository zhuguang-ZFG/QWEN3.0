"""SMS / login-code verification for device app auth."""

from __future__ import annotations

import secrets
import warnings
from typing import Any

from fastapi.responses import JSONResponse

from config import settings
from device_logic.http import err, str_field

warnings.warn(
    "device_logic.sms is deprecated; do not use in production",
    DeprecationWarning,
    stacklevel=2,
)

SMS_EXPIRES_SECONDS = 300


def configured_login_code() -> str:
    # 安全风险：settings.DEVICE.login_code 是静态全局共享口令方案（已废弃）。
    # 所有设备共用同一口令，不可用于生产鉴权。
    return settings.DEVICE.login_code


def captcha_required() -> bool:
    return settings.DEVICE.captcha_required


def login_code_error() -> JSONResponse | None:
    if configured_login_code():
        return None
    return err(503, "SMS verification code is not configured", 503)


def validate_login_code(code: str) -> bool:
    expected = configured_login_code()
    return bool(expected and code and secrets.compare_digest(code, expected))


def extract_captcha_fields(body: dict[str, Any]) -> tuple[str, str]:
    return str_field(body, "captchaId", "captcha_id"), str_field(body, "captcha")


def sms_verification_payload(phone: str) -> dict[str, object]:
    return {"phone": phone, "mock": True, "expiresIn": SMS_EXPIRES_SECONDS}
