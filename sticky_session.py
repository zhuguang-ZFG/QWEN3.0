"""
LiMa Sticky Session — 会话亲和路由
解决多轮对话路由到不同后端导致上下文断裂的问题。

设计参考: Olla (github.com/thushan/olla)
核心: 对话前缀 hash → 粘在同一后端 → TTL 滑动续期
"""

import hashlib
import time
import threading

_lock = threading.Lock()
_store: dict[str, tuple[str, float]] = {}
MAX_SESSIONS = 2000
IDLE_TTL = 300  # 5 分钟无活动过期
PREFIX_BYTES = 512


def compute_key(model: str, messages_json: str) -> str:
    """计算会话亲和 key: model + 对话前缀 hash"""
    prefix = messages_json[:PREFIX_BYTES].encode("utf-8", errors="ignore")
    h = hashlib.blake2b(prefix, digest_size=8).hexdigest()
    return f"{model}:{h}"


def get_pinned_backend(key: str) -> str | None:
    """查找已绑定的后端，命中则续期"""
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        backend, expire_at = entry
        if time.monotonic() > expire_at:
            del _store[key]
            return None
        _store[key] = (backend, time.monotonic() + IDLE_TTL)
        return backend


def pin_backend(key: str, backend: str):
    """绑定 key 到后端"""
    with _lock:
        if len(_store) >= MAX_SESSIONS:
            _evict_oldest()
        _store[key] = (backend, time.monotonic() + IDLE_TTL)


def unpin(key: str):
    """后端死亡时解绑，下次重新选路"""
    with _lock:
        _store.pop(key, None)


def _evict_oldest():
    """淘汰最早过期的条目"""
    if not _store:
        return
    oldest_key = min(_store, key=lambda k: _store[k][1])
    del _store[oldest_key]
