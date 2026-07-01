#!/usr/bin/env python3
"""Response examples for authentication and user-account endpoints.

手机号鉴权（register/sms-verification/captcha）于 2026-07-02 slimdown P2-16 移除。
保留：login、me、account/delete、change-password（微信与邮箱鉴权通用）。
"""

from __future__ import annotations

from typing import Any

from .shared import uuid


def _resp_auth_login() -> Any:
    return {"access_token": uuid("tok"), "token_type": "bearer", "expires_in": 3600}


def _resp_auth_me() -> Any:
    return {"id": uuid("usr"), "phone": "+86-13800000000", "nickname": "User"}


def _resp_auth_account_delete() -> Any:
    return {"success": True}


def _resp_auth_change_password() -> Any:
    return {"success": True}
