"""Device authentication helpers."""

from __future__ import annotations

import os
from hmac import compare_digest


def configured_device_tokens() -> dict[str, str]:
    """Return device_id -> token entries from LIMA_DEVICE_TOKENS.

    Format: dev_a=token-a,dev_b=token-b. Newlines and semicolons are also
    accepted for ops convenience.
    """
    raw = os.environ.get("LIMA_DEVICE_TOKENS", "")
    tokens: dict[str, str] = {}
    for chunk in raw.replace("\n", ",").replace(";", ",").split(","):
        item = chunk.strip()
        if not item or "=" not in item:
            continue
        device_id, token = item.split("=", 1)
        device_id = device_id.strip()
        token = token.strip()
        if device_id and token:
            tokens[device_id] = token
    return tokens


def validate_device_token(device_id: str, token: str) -> bool:
    expected = configured_device_tokens().get(device_id)
    if not expected or not token:
        return False
    return compare_digest(expected, token)


def token_configured() -> bool:
    return bool(configured_device_tokens())
