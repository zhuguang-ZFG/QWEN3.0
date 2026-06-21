"""Backward-compatible re-export — canonical implementation in device_logic.auth."""

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
