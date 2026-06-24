"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


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
