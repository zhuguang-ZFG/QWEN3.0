"""Backward-compatible re-export — canonical implementation in device_logic.sms."""

from device_logic.sms import (
    SMS_EXPIRES_SECONDS,
    captcha_required,
    configured_login_code,
    extract_captcha_fields,
    login_code_error,
    sms_verification_payload,
    validate_login_code,
)

__all__ = [
    "SMS_EXPIRES_SECONDS",
    "captcha_required",
    "configured_login_code",
    "extract_captcha_fields",
    "login_code_error",
    "sms_verification_payload",
    "validate_login_code",
]
