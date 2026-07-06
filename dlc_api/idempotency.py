"""S10 idempotency dedupe for /dlc/tasks/dispatch — Redis SET NX EX claim/release.

Extracted from ``dlc_api.routes`` to keep that module under the 300-line limit.
The claim is taken *before* the dispatch work runs, so any failure before the
command actually reaches the device queue must release the key (see
``release_idempotency_key``) — standard idempotency semantics: only a
successful dispatch keeps the key, a failure stays retryable.
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import REDIS

logger = logging.getLogger(__name__)

# S10: idempotency dedupe TTL (seconds) for the Redis SET NX EX claim.
IDEMPOTENCY_TTL = 600

# review Warning #3：idempotency 路径复用模块级 Redis client，避免每次 dispatch
# 都新建连接池（connection churn）。沿用 rate_limiter_redis._get_client 的惰性单例惯例。
_idem_client: Any | None = None
_idem_prefix: str = ""
_idem_client_failed = False


def _get_idempotency_client() -> tuple[Any, str] | None:
    """Return a cached (client, prefix) for idempotency dedupe, or None when unavailable."""
    global _idem_client, _idem_prefix, _idem_client_failed
    if _idem_client is not None:
        return _idem_client, _idem_prefix
    if _idem_client_failed:
        return None
    try:
        from device_gateway.redis_store_helpers import connect_redis

        _idem_client, _idem_prefix = connect_redis(
            REDIS.device_redis_url, "dlc_idempotency", key_prefix="lima:dlc:idem"
        )
    except Exception as exc:
        _idem_client_failed = True
        logger.warning("S10: idempotency Redis unavailable (%s); allowing dispatch without dedupe", exc)
        return None
    return _idem_client, _idem_prefix


def claim_idempotency_key(idem_key: str, task_id: str, *, ttl: int = IDEMPOTENCY_TTL) -> bool:
    """S10: atomically claim an idempotency key. Returns True on first use, False on replay.

    Uses Redis SET NX EX for cross-worker dedupe. When Redis is unavailable we
    log a warning and allow the request through (fail-open) rather than blocking
    a legitimate dispatch on infra failure — a duplicate is less harmful than a
    dropped command, and the warning surfaces the degraded state (no silent
    degradation).
    """
    cached = _get_idempotency_client()
    if cached is None:
        return True
    client, prefix = cached
    try:
        claimed = client.set(f"{prefix}:{idem_key}", task_id or "1", nx=True, ex=ttl)
    except Exception as exc:
        logger.warning("S10: idempotency SET NX failed (%s); allowing dispatch without dedupe", exc)
        return True
    return bool(claimed)


def release_idempotency_key(idem_key: str) -> None:
    """S10: release a previously claimed idempotency key so the caller can retry.

    Called when a claimed dispatch fails before the command is actually sent
    (path build error, device offline, dispatch rejected). Standard idempotency
    semantics: only a *successful* dispatch should keep the key; a failure must
    be retryable with the same key. Best-effort — a DEL failure just leaves the
    key to expire naturally via its TTL.
    """
    cached = _get_idempotency_client()
    if cached is None:
        return
    client, prefix = cached
    try:
        client.delete(f"{prefix}:{idem_key}")
    except Exception as exc:
        logger.warning("S10: idempotency key release failed (%s); key will expire via TTL", exc)
