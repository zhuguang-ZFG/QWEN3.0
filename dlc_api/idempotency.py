"""S10 idempotency dedupe for /dlc/tasks/dispatch — Redis SET NX EX claim/release.

Extracted from ``dlc_api.routes`` to keep that module under the 300-line limit.
The claim is taken *before* the dispatch work runs, so any failure before the
command actually reaches the device queue must release the key (see
``release_idempotency_key``) — standard idempotency semantics: only a
successful dispatch keeps the key, a failure stays retryable.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from config.settings import REDIS

logger = logging.getLogger(__name__)

# S10: idempotency dedupe TTL (seconds) for the Redis SET NX EX claim.
IDEMPOTENCY_TTL = 600

# Two-barrier dedupe (业界模式：AWS Powertools in-progress 幂等 / Kafka 双屏障管道)。
# 复刻本仓库 rate_limiter.py 的 L1(进程内)+L2(Redis) 分层：Redis(L2) 可用时以其
# 为权威；Redis 不可用时回退 L1 进程内 TTL 字典，至少挡住同 worker 重复 dispatch，
# 把 fail-open 的"完全无去重"收窄成"挡住同 worker 重复"。不翻转 fail-open 语义。
# server_dlc:app 单 worker 启动，故 L1 覆盖单节点几乎全部流量。
_l1_store: dict[str, tuple[str, float]] = {}
_l1_lock = threading.Lock()


def _l1_claim(idem_key: str, value: str, ttl: int) -> bool:
    """L1 兜底 claim：未过期条目存在则视为重复(False)，否则占用并放行(True)。"""
    now = time.monotonic()
    with _l1_lock:
        entry = _l1_store.get(idem_key)
        if entry is not None and entry[1] > now:
            return False
        _l1_store[idem_key] = (value, now + ttl)
        return True


def _l1_release(idem_key: str, expected: str) -> None:
    """L1 兜底 release：仅当条目 value 匹配才清除（CAD，防误删他人 key）。"""
    with _l1_lock:
        entry = _l1_store.get(idem_key)
        if entry is not None and entry[0] == expected:
            _l1_store.pop(idem_key, None)


# review Warning #3：idempotency 路径复用模块级 Redis client，避免每次 dispatch
# 都新建连接池（connection churn）。沿用 rate_limiter_redis._get_client 的惰性单例惯例。
_idem_client: Any | None = None
_idem_prefix: str = ""
_idem_client_failed = False
# Cursor 复审：失败后记录时间戳，冷却窗口过后允许重连一次，避免永久粘滞
# （Redis 短暂抖动恢复后能自愈），窗口内仍不重试以保留连接超时保护。
_idem_client_failed_at = 0.0
_IDEM_RETRY_COOLDOWN = 30.0


def _get_idempotency_client() -> tuple[Any, str] | None:
    """Return a cached (client, prefix) for idempotency dedupe, or None when unavailable."""
    global _idem_client, _idem_prefix, _idem_client_failed, _idem_client_failed_at
    if _idem_client is not None:
        return _idem_client, _idem_prefix
    if _idem_client_failed and (time.monotonic() - _idem_client_failed_at) < _IDEM_RETRY_COOLDOWN:
        # 冷却窗口内：不重试，继续放行（避免每次 dispatch 卡在 Redis 连接超时上）。
        return None
    try:
        from device_gateway.redis_store_helpers import connect_redis

        _idem_client, _idem_prefix = connect_redis(
            REDIS.device_redis_url, "dlc_idempotency", key_prefix="lima:dlc:idem"
        )
    except Exception as exc:
        _idem_client_failed = True
        _idem_client_failed_at = time.monotonic()
        logger.warning("S10: idempotency Redis unavailable (%s); allowing dispatch without dedupe", exc)
        return None
    _idem_client_failed = False
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
        # Redis(L2) 不可用 → 回退 L1 进程内屏障（挡住同 worker 重复）。
        return _l1_claim(idem_key, task_id or "1", ttl)
    client, prefix = cached
    try:
        claimed = client.set(f"{prefix}:{idem_key}", task_id or "1", nx=True, ex=ttl)
    except Exception as exc:
        logger.warning("S10: idempotency SET NX failed (%s); falling back to L1 dedupe", exc)
        return _l1_claim(idem_key, task_id or "1", ttl)
    return bool(claimed)


# Lua: compare-and-delete — only DEL when the stored value matches ARGV[1].
# Prevents deleting a key that a *different* request re-claimed after the
# original claim's TTL expired (lost-lock / delete-someone-else's-lock bug).
_CAD_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

_cad_scripts: dict[int, Any] = {}


def _get_cad_script(client: Any) -> Any:
    cid = id(client)
    script = _cad_scripts.get(cid)
    if script is None:
        script = client.register_script(_CAD_LUA)
        _cad_scripts[cid] = script
    return script


def release_idempotency_key(idem_key: str, expected_value: str) -> None:
    """S10: release a claimed key **only if** it still holds ``expected_value``.

    Called when a claimed dispatch fails before the command is actually sent
    (path build error, device offline, dispatch rejected). Standard idempotency
    semantics: only a *successful* dispatch should keep the key; a failure must
    be retryable with the same key.

    Compare-and-delete (matching the claim's ``request_id``) is required so a
    slow-then-failed request cannot delete a key that a *different* request
    re-claimed after the original TTL expired — otherwise that later request's
    dedupe guard is silently dropped and the device could execute twice.
    Best-effort — any Redis error just leaves the key to expire via its TTL.
    """
    cached = _get_idempotency_client()
    if cached is None:
        # Redis(L2) 不可用 → 释放 L1 进程内屏障（CAD：仅 value 匹配才清除）。
        _l1_release(idem_key, expected_value or "1")
        return
    client, prefix = cached
    full_key = f"{prefix}:{idem_key}"
    expected = expected_value or "1"
    try:
        if hasattr(client, "register_script"):
            _get_cad_script(client)(keys=[full_key], args=[expected])
        else:
            # Non-atomic fallback for test fakes: GET then DEL when it matches.
            if client.get(full_key) == expected:
                client.delete(full_key)
    except Exception as exc:
        logger.warning("S10: idempotency key release failed (%s); key will expire via TTL", exc)
