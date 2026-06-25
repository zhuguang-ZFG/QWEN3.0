"""Email/password helpers for device app authentication."""

from __future__ import annotations

import re
from typing import Any

from device_logic.db import connect

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def is_valid_email(value: str) -> bool:
    return bool(value and _EMAIL_RE.match(value))


def account_by_email(email: str) -> Any | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM v2_account WHERE email=? AND status='active'", (email,)).fetchone()
