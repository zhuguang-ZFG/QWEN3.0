"""opencode_session_cache.py — OpenCode 会话后端亲和缓存。

缓存 OpenCode 会话的后端选择决策，减少路由开销。当同一会话连续发送请求时，
优先复用上次成功的后端，避免每次都重新做健康检查 + P2C + 推测路由。

设计原则:
- 会话粒度：基于 X-OpenCode-Session-Id 头（来自 opencode_request_headers.py）
- 成功才缓存：只缓存成功响应的后端（避免缓存坏后端）
- TTL 短期：5 分钟过期，避免绑定到长期不健康的后端
- 健康前置：使用缓存前仍需检查健康状态（熔断器）
- 降级友好：缓存失效时自动走完整路由逻辑

与 sticky_session.py 的区别:
- sticky_session: 基于 IP + backend name，用于多轮对话（通用）
- opencode_session_cache: 基于 session ID，包含完整路由决策（OpenCode 专属）
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

_log = logging.getLogger(__name__)

# ── 缓存结构 ──────────────────────────────────────────────────────────────
# session_id → {backend, timestamp, success_count}
_cache: dict[str, dict] = {}
_lock = threading.Lock()

# 配置参数
TTL_SECONDS = 300  # 5 分钟
MAX_CACHE_SIZE = 1000  # 最多缓存 1000 个会话


def get_cached_backend(session_id: str) -> Optional[str]:
    """获取会话的缓存后端（如果未过期）。"""
    if not session_id:
        return None

    with _lock:
        entry = _cache.get(session_id)
        if not entry:
            return None

        # 检查是否过期
        if time.time() - entry["timestamp"] > TTL_SECONDS:
            _cache.pop(session_id, None)
            _log.debug("session cache expired: %s", session_id[:16])
            return None

        _log.debug(
            "session cache hit: %s → %s (success=%d)",
            session_id[:16],
            entry["backend"],
            entry["success_count"],
        )
        return entry["backend"]


def record_success(session_id: str, backend: str) -> None:
    """记录成功响应，更新缓存。"""
    if not session_id or not backend:
        return

    with _lock:
        # LRU 淘汰：缓存满时删除最旧的条目
        if len(_cache) >= MAX_CACHE_SIZE:
            oldest = min(_cache.items(), key=lambda x: x[1]["timestamp"])
            _cache.pop(oldest[0], None)
            _log.debug("session cache evicted oldest: %s", oldest[0][:16])

        # 更新或创建缓存条目
        if session_id in _cache:
            _cache[session_id]["backend"] = backend
            _cache[session_id]["timestamp"] = time.time()
            _cache[session_id]["success_count"] += 1
        else:
            _cache[session_id] = {
                "backend": backend,
                "timestamp": time.time(),
                "success_count": 1,
            }
            _log.debug("session cache new: %s → %s", session_id[:16], backend)


def invalidate_session(session_id: str) -> None:
    """失效会话缓存（当后端失败时调用）。"""
    if not session_id:
        return

    with _lock:
        if session_id in _cache:
            _log.debug("session cache invalidated: %s", session_id[:16])
            _cache.pop(session_id)


def get_cache_stats() -> dict:
    """返回缓存统计信息（调试用）。"""
    with _lock:
        return {
            "size": len(_cache),
            "sessions": [
                {
                    "id": sid[:16],
                    "backend": entry["backend"],
                    "age_seconds": int(time.time() - entry["timestamp"]),
                    "success_count": entry["success_count"],
                }
                for sid, entry in sorted(
                    _cache.items(), key=lambda x: x[1]["timestamp"], reverse=True
                )[:10]
            ],
        }


def clear_cache() -> None:
    """清空所有缓存（测试用）。"""
    with _lock:
        _cache.clear()
        _log.info("session cache cleared")
