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
from runtime_env import is_production_runtime

logger = logging.getLogger(__name__)

# S10: idempotency dedupe TTL (seconds) for the Redis SET NX EX claim.
IDEMPOTENCY_TTL = 600


class IdempotencyUnavailableError(Exception):
    """Raised in production when the idempotency store cannot claim a key."""


# Two-barrier dedupe (业界模式：AWS Powertools in-progress 幂等 / Kafka 双屏障管道)。
# 复刻本仓库 rate_limiter.py 的 L1(进程内)+L2(Redis) 分层：Redis(L2) 可用时以其
# 为权威；非生产且 Redis 不可用时回退 L1 进程内 TTL 字典（fail-open + L1）。
# 生产路径 Redis 缺失/SET 失败 → raise（fail-closed），由路由返回 503。
# server_dlc:app 单 worker 启动，故非生产 L1 覆盖单节点几乎全部流量。
_l1_store: dict[str, tuple[str, float]] = {}
_l1_lock = threading.Lock()
# L1 上限：成功 dispatch 的 idem_key 几乎不重复，过期条目只在同 key 复用时覆盖，
# 故 _l1_store 会无界增长。达上限时惰性清扫过期条目（仍超限则丢弃最旧），
# 既保留 Redis 抖动恢复窗口的 L1 barrier，又消除长跑 OOM。
_L1_MAX_ENTRIES = 4096


def _l1_sweep(now: float) -> None:
    """惰性清扫：清掉所有过期条目；仍超上限则按最旧丢弃（调用方持锁）。"""
    if len(_l1_store) < _L1_MAX_ENTRIES:
        return
    for key in [k for k, (_v, exp) in _l1_store.items() if exp <= now]:
        _l1_store.pop(key, None)
    overflow = len(_l1_store) - _L1_MAX_ENTRIES + 1
    if overflow > 0:
        # 未过期条目大量堆积（罕见）：丢弃最旧的若干个腾出空间。
        oldest = sorted(_l1_store.items(), key=lambda kv: kv[1][1])[:overflow]
        for key, _ in oldest:
            _l1_store.pop(key, None)


def _l1_claim(idem_key: str, value: str, ttl: int) -> bool:
    """L1 兜底 claim：未过期条目存在则视为重复(False)，否则占用并放行(True)。"""
    now = time.monotonic()
    with _l1_lock:
        _l1_sweep(now)
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
        logger.warning("S10: idempotency Redis unavailable (%s); using L1 in-process dedupe", exc)
        return None
    _idem_client_failed = False
    return _idem_client, _idem_prefix


def claim_idempotency_key(idem_key: str, task_id: str, *, ttl: int = IDEMPOTENCY_TTL) -> bool:
    """Atomically claim an idempotency key. True on first use, False on replay.

    Redis SET NX EX is the cross-worker authority. Non-production falls back to
    L1 in-process dedupe when Redis is down (fail-open + L1). Production raises
    ``IdempotencyUnavailableError`` instead of admitting the dispatch.
    """
    expected = task_id or "1"
    if not _l1_claim(idem_key, expected, ttl):
        return False
    cached = _get_idempotency_client()
    if cached is None:
        if is_production_runtime():
            _l1_release(idem_key, expected)
            raise IdempotencyUnavailableError("idempotency store unavailable")
        return True
    client, prefix = cached
    try:
        claimed = client.set(f"{prefix}:{idem_key}", expected, nx=True, ex=ttl)
    except Exception as exc:
        if is_production_runtime():
            _l1_release(idem_key, expected)
            raise IdempotencyUnavailableError("idempotency store unavailable") from exc
        logger.warning("S10: idempotency SET NX failed (%s); using L1 in-process dedupe", exc)
        return True
    if not claimed:
        _l1_release(idem_key, expected)
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
    _l1_release(idem_key, expected)
    try:
        if hasattr(client, "register_script"):
            _get_cad_script(client)(keys=[full_key], args=[expected])
        else:
            # Non-atomic fallback for test fakes: GET then DEL when it matches.
            if client.get(full_key) == expected:
                client.delete(full_key)
    except Exception as exc:
        logger.warning("S10: idempotency key release failed (%s); key will expire via TTL", exc)
