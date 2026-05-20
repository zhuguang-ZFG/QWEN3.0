"""
LiMa Semantic Cache — 精确匹配缓存 (非向量相似度)
参考: OmniRoute (SHA-256 + LRU + temperature=0)

设计:
- key = SHA-256(model + messages + temperature)
- 仅缓存 temperature=0 的请求 (确定性输出)
- 两级存储: LRU 内存 (可配容量) + 可选持久化
- 命中则零延迟返回，不消耗后端配额
"""

import time
import hashlib
import json
import threading
from collections import OrderedDict
from typing import Optional

_lock = threading.Lock()

DEFAULT_MAX_SIZE = 200
DEFAULT_TTL = 3600  # 1 小时过期


class SemanticCache:
    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, ttl: int = DEFAULT_TTL):
        self._store: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    def make_key(self, model: str, messages: list, temperature: float = 0) -> str:
        """生成缓存 key。非 temperature=0 返回空字符串(不缓存)"""
        if temperature != 0:
            return ""
        payload = json.dumps(
            {"model": model, "messages": messages, "temperature": temperature},
            sort_keys=True, ensure_ascii=False
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, key: str) -> Optional[str]:
        """查缓存，命中返回响应文本，未命中返回 None"""
        if not key:
            return None
        with _lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expire_at = entry
            if time.monotonic() > expire_at:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def put(self, key: str, value: str):
        """写入缓存"""
        if not key:
            return
        with _lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = (value, time.monotonic() + self._ttl)
            else:
                if len(self._store) >= self._max_size:
                    self._store.popitem(last=False)
                self._store[key] = (value, time.monotonic() + self._ttl)

    def stats(self) -> dict:
        """缓存统计"""
        with _lock:
            total = self._hits + self._misses
            rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{rate:.1f}%",
            }


# 全局实例
_cache = SemanticCache()


def get(model: str, messages: list, temperature: float = 0) -> Optional[str]:
    key = _cache.make_key(model, messages, temperature)
    return _cache.get(key)


def put(model: str, messages: list, temperature: float, response: str):
    key = _cache.make_key(model, messages, temperature)
    _cache.put(key, response)


def stats() -> dict:
    return _cache.stats()
