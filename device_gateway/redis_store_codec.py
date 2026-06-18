"""JSON encode/decode helpers for Redis-backed device task store."""

from __future__ import annotations

import json
from typing import Any


def encode_redis_json(value: dict[str, Any]) -> str:
    """Serialize a dict to a compact JSON string for Redis storage."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def decode_redis_json(value: str | bytes) -> dict[str, Any]:
    """Deserialize a Redis JSON value, rejecting non-dict payloads."""
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    data = json.loads(value)
    if not isinstance(data, dict):
        raise RuntimeError(f"expected Redis JSON object, got: {data!r}")
    return data
