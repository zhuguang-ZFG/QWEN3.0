"""
LiMa Key Pool — SWRR 权重轮转 + 分级冷却 + 自动拉黑恢复
参考: GPT-Load (SWRR) + One Balance (分钟/天级冷却)

设计:
- 每个 provider 维护一组 key
- SWRR 算法选 key (和 Nginx 一致)
- 429 → 分钟级冷却 (解析 Retry-After)
- 连续 N 次 429 → 天级冷却 (到次日 0 点)
- 401/403 → 永久拉黑 (需手动恢复)
"""

import time
import threading
import os
import re
import hashlib
from typing import Optional
from dataclasses import dataclass, field

MINUTE_COOLDOWN = 60
DAY_COOLDOWN_HOUR = 24 * 3600
CONSECUTIVE_429_THRESHOLD = 5


@dataclass
class KeyEntry:
    key: str
    weight: int = 1
    current_weight: int = 0
    status: str = "active"  # active | cooled | blocked
    cool_until: float = 0
    consecutive_429: int = 0


class KeyPool:
    """单个 provider 的 key 池"""

    def __init__(self, provider: str, keys: list[dict]):
        self.provider = provider
        self._lock = threading.Lock()
        self.entries: list[KeyEntry] = []
        for k in keys:
            self.entries.append(KeyEntry(
                key=k["key"],
                weight=k.get("weight", 1),
            ))

    def select(self) -> Optional[str]:
        """SWRR 选择一个可用 key"""
        with self._lock:
            now = time.monotonic()
            active = [e for e in self.entries
                      if e.status == "active" or
                      (e.status == "cooled" and now > e.cool_until)]
            for e in active:
                if e.status == "cooled":
                    e.status = "active"
                    e.consecutive_429 = 0

            if not active:
                return None

            total = sum(e.weight for e in active)
            best = None
            for e in active:
                e.current_weight += e.weight
                if best is None or e.current_weight > best.current_weight:
                    best = e
            best.current_weight -= total
            return best.key

    def report_success(self, key: str):
        """请求成功"""
        with self._lock:
            e = self._find(key)
            if e:
                e.consecutive_429 = 0

    def report_failure(self, key: str, error_code: int, retry_after: int = 0):
        """请求失败，根据错误码决定冷却策略"""
        with self._lock:
            e = self._find(key)
            if not e:
                return

            if error_code in (401, 403):
                e.status = "blocked"
                return

            if error_code == 429:
                e.consecutive_429 += 1
                if e.consecutive_429 >= CONSECUTIVE_429_THRESHOLD:
                    e.status = "cooled"
                    e.cool_until = time.monotonic() + DAY_COOLDOWN_HOUR
                else:
                    e.status = "cooled"
                    ttl = retry_after if retry_after > 0 else MINUTE_COOLDOWN
                    e.cool_until = time.monotonic() + ttl

    def get_active_count(self) -> int:
        with self._lock:
            now = time.monotonic()
            return sum(1 for e in self.entries
                       if e.status == "active" or
                       (e.status == "cooled" and now > e.cool_until))

    def snapshot(self) -> dict:
        with self._lock:
            now = time.monotonic()
            entries = []
            counts = {"active": 0, "cooled": 0, "blocked": 0}
            for e in self.entries:
                status = e.status
                if status == "cooled" and now > e.cool_until:
                    status = "active"
                counts[status] = counts.get(status, 0) + 1
                entries.append({
                    "key_id": _fingerprint_key(e.key),
                    "weight": e.weight,
                    "status": status,
                    "cool_remaining_sec": max(0, int(e.cool_until - now)),
                    "consecutive_429": e.consecutive_429,
                })
            return {
                "provider": self.provider,
                "total": len(self.entries),
                "active": counts.get("active", 0),
                "cooled": counts.get("cooled", 0),
                "blocked": counts.get("blocked", 0),
                "entries": entries,
            }

    def _find(self, key: str) -> Optional[KeyEntry]:
        for e in self.entries:
            if e.key == key:
                return e
        return None


# ─── 全局 Key Pool 管理 ─────────────────────────────────────────────────────

_pools: dict[str, KeyPool] = {}


def _fingerprint_key(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
    suffix = key[-4:] if len(key) >= 4 else key
    return f"{digest}:{suffix}"


def _env_name(provider: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", provider).strip("_").upper()
    return f"LIMA_KEY_POOL_{safe}"


def _parse_env_keys(raw: str) -> list[dict]:
    entries = []
    for item in re.split(r"[\n,;]+", raw):
        item = item.strip()
        if not item:
            continue
        key, sep, weight_text = item.rpartition(":")
        if sep and key:
            try:
                weight = max(1, int(weight_text))
            except ValueError:
                key, weight = item, 1
        else:
            key, weight = item, 1
        entries.append({"key": key, "weight": weight})
    return entries


def register_pool(provider: str, keys: list[dict]):
    """注册一个 provider 的 key 池"""
    _pools[provider] = KeyPool(provider, keys)


def register_env_pool(provider: str, env_name: str = "") -> bool:
    raw = os.environ.get(env_name or _env_name(provider), "")
    keys = _parse_env_keys(raw)
    if not keys:
        return False
    register_pool(provider, keys)
    return True


def ensure_env_pool(provider: str) -> bool:
    if provider in _pools:
        return True
    return register_env_pool(provider)


def clear_pools():
    _pools.clear()


def pool_snapshot(provider: str = "") -> dict:
    if provider:
        pool = _pools.get(provider)
        return pool.snapshot() if pool else {
            "provider": provider,
            "total": 0,
            "active": 0,
            "cooled": 0,
            "blocked": 0,
            "entries": [],
        }
    return {
        "providers": {
            name: pool.snapshot()
            for name, pool in sorted(_pools.items())
        }
    }


def get_key(provider: str) -> Optional[str]:
    """获取一个可用 key"""
    pool = _pools.get(provider)
    if not pool:
        return None
    return pool.select()


def report_key_result(provider: str, key: str, success: bool,
                      error_code: int = 0, retry_after: int = 0):
    """上报 key 使用结果"""
    pool = _pools.get(provider)
    if not pool:
        return
    if success:
        pool.report_success(key)
    else:
        pool.report_failure(key, error_code, retry_after)
