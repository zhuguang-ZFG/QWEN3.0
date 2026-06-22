"""JSON encode/decode helpers and shared Redis connection utility.

Ponytail: three separate __init__ methods did the same redis.from_url dance.
Shared here until a real connection pool abstraction is warranted.
"""

from __future__ import annotations

import json
import logging
from typing import Any


def connect_redis(
    redis_url: str,
    label: str,
    *,
    client: Any | None = None,
    key_prefix: str = "lima",
) -> tuple[Any, str]:
    """Create or validate a Redis client. Returns (client, prefix).

    Ponytail: three stores each started with this same try/import/from_url
    pattern. Extracted here — upgrade to a connection pool when Redis
    throughput becomes a bottleneck.
    """
    if client is None:
        try:
            import redis as _redis_mod
        except ImportError as exc:
            raise RuntimeError(f"redis package required for {label}") from exc
        client = _redis_mod.Redis.from_url(redis_url, decode_responses=True)
    return client, key_prefix.rstrip(":")


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
