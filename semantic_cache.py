"""
LiMa Semantic Cache — SHA-256 精确匹配 + SQLite 持久化
参考: OmniRoute (SHA-256 + LRU + temperature=0)

设计:
- key = SHA-256(model + messages + temperature)
- 仅缓存 temperature=0 的请求 (确定性输出)
- 两级存储: LRU 内存热缓存 + SQLite 持久化冷缓存
- 命中则零延迟返回，不消耗后端配额
- 重启后自动从 SQLite 恢复热缓存
"""

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from collections import OrderedDict
from typing import Optional

_log = logging.getLogger(__name__)
_lock = threading.Lock()

DEFAULT_MAX_SIZE = 500
DEFAULT_TTL = 86400  # 24 小时
_DB_PATH = os.environ.get("LIMA_CACHE_DB", "data/semantic_cache.db")


class SemanticCache:
    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, ttl: int = DEFAULT_TTL):
        self._store: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0
        self._db_write_errors = 0
        self._db = self._init_db()
        self._load_from_db()

    def _init_db(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(_DB_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cache "
            "(key TEXT PRIMARY KEY, value TEXT, created_at REAL)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON cache(created_at)")
        conn.commit()
        return conn

    def _load_from_db(self) -> None:
        now = time.time()
        cutoff = now - self._ttl
        rows = self._db.execute(
            "SELECT key, value, created_at FROM cache "
            "WHERE created_at > ? ORDER BY created_at DESC LIMIT ?",
            (cutoff, self._max_size),
        ).fetchall()
        for key, value, created_at in reversed(rows):
            expire_at = created_at + self._ttl
            self._store[key] = (value, expire_at)

    def make_key(self, model: str, messages: list, temperature: float = 0) -> str:
        if temperature != 0:
            return ""
        payload = json.dumps(
            {"model": model, "messages": messages, "temperature": temperature},
            sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, key: str) -> Optional[str]:
        if not key:
            return None
        with _lock:
            entry = self._store.get(key)
            if entry is None:
                row = self._db.execute(
                    "SELECT value, created_at FROM cache WHERE key = ?", (key,)
                ).fetchone()
                if row and (time.time() - row[1]) < self._ttl:
                    self._store[key] = (row[0], row[1] + self._ttl)
                    self._hits += 1
                    return row[0]
                self._misses += 1
                return None
            value, expire_at = entry
            if time.time() > expire_at:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def put(self, key: str, value: str):
        if not key:
            return
        with _lock:
            now = time.time()
            if key in self._store:
                self._store.move_to_end(key)
            else:
                if len(self._store) >= self._max_size:
                    self._store.popitem(last=False)
            self._store[key] = (value, now + self._ttl)
            try:
                self._db.execute(
                    "INSERT OR REPLACE INTO cache (key, value, created_at) VALUES (?, ?, ?)",
                    (key, value, now),
                )
                self._db.commit()
            except Exception as exc:
                self._db_write_errors += 1
                _log.warning(
                    "semantic_cache db write failed key_prefix=%s err=%s",
                    key[:12],
                    type(exc).__name__,
                )

    def stats(self) -> dict:
        with _lock:
            total = self._hits + self._misses
            rate = (self._hits / total * 100) if total > 0 else 0
            db_size = self._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            return {
                "size": len(self._store),
                "db_size": db_size,
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{rate:.1f}%",
                "db_write_errors": self._db_write_errors,
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
