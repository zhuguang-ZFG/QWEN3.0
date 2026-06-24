#!/usr/bin/env python3
"""Response examples for authentication and user-account endpoints."""

from __future__ import annotations

from typing import Any

from .shared import uuid


def _resp_auth_login() -> Any:
    return {"access_token": uuid("tok"), "token_type": "bearer", "expires_in": 3600}


def _resp_auth_me() -> Any:
    return {"id": uuid("usr"), "phone": "+86-13800000000", "nickname": "User"}


def _resp_auth_register() -> Any:
    return {"id": uuid("usr"), "message": "registered"}


def _resp_auth_sms_verification() -> Any:
    return {"success": True, "message": "code sent"}


def _resp_auth_account_delete() -> Any:
    return {"success": True}


def _resp_auth_captcha() -> Any:
    return {"captcha_id": uuid("cap"), "image_url": "https://example/captcha.png"}


def _resp_auth_change_password() -> Any:
    return {"success": True}
