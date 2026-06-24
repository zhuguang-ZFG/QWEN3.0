"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


from device_logic.auth import (
    _BCRYPT_IMPORT_ERROR,
    _JWT_IMPORT_ERROR,
    _hash_password,
    _verify_password,
    account_payload,
    authorize,
    jwt,
    jwt_secret,
    make_token,
)

__all__ = [
    "_BCRYPT_IMPORT_ERROR",
    "_JWT_IMPORT_ERROR",
    "_hash_password",
    "_verify_password",
    "account_payload",
    "authorize",
    "jwt",
    "jwt_secret",
    "make_token",
]
