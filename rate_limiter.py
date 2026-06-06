"""rate_limiter.py — 滑动窗口 IP 限流

单进程部署下工作正常。多 Worker 场景需迁移到 Redis 共享存储。
"""
import logging
import time
from collections import defaultdict

_log = logging.getLogger(__name__)

WINDOW = 60
MAX_PER_WINDOW = 20
_STALE_TTL = 300  # seconds before an IP entry is considered stale
_CLEANUP_INTERVAL = 60  # seconds between automatic stale evictions
_last_cleanup = 0.0

_requests: dict[str, list[float]] = defaultdict(list)


def _evict_stale(now: float) -> int:
    """Remove IP entries with no requests within _STALE_TTL. Returns count removed."""
    stale_ips = [ip for ip, ts in _requests.items() if not ts or now - ts[-1] > _STALE_TTL]
    for ip in stale_ips:
        del _requests[ip]
    return len(stale_ips)


def check_rate_limit(ip: str, multiplier: int = 1) -> bool:
    """返回 True 表示允许，False 表示超限。multiplier 用于 IDE 客户端提高配额。"""
    global _last_cleanup
    now = time.time()

    # Periodic stale-entry eviction to prevent unbounded dict growth
    if now - _last_cleanup > _CLEANUP_INTERVAL:
        removed = _evict_stale(now)
        if removed:
            _log.debug("rate_limiter: evicted %d stale IP entries", removed)
        _last_cleanup = now

    _requests[ip] = [t for t in _requests[ip] if now - t < WINDOW]
    limit = MAX_PER_WINDOW * multiplier
    if len(_requests[ip]) >= limit:
        return False
    _requests[ip].append(now)
    return True


def get_usage(ip: str) -> dict:
    """返回当前 IP 的使用情况（调试用）。"""
    now = time.time()
    recent = [t for t in _requests[ip] if now - t < WINDOW]
    return {"ip": ip, "requests_in_window": len(recent), "limit": MAX_PER_WINDOW}


def reset(ip: str = None):
    """重置限流状态（测试用）。"""
    if ip:
        _requests.pop(ip, None)
    else:
        _requests.clear()
