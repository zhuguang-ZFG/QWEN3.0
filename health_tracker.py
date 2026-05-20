"""
LiMa Health Tracker — 被动追踪 + 主动探活
- 被动: 每次真实请求自动更新 health_map (零成本)
- 主动: 后台线程对 dead/suspicious 后端发探针 (省配额)
- 冷却: TTL cache 实现 (参考 LiteLLM, 默认 5s)
"""

import time
import threading
from typing import Optional

COOLDOWN_TTL = 5
FAILURE_THRESHOLD_PERCENT = 0.5
FAILURE_THRESHOLD_MIN_REQUESTS = 5

_lock = threading.Lock()
_health_map: dict[str, str] = {}
_cooldown_cache: dict[str, float] = {}
_failure_counts: dict[str, int] = {}
_request_counts: dict[str, int] = {}
_latency_windows: dict[str, list] = {}

LATENCY_WINDOW_SIZE = 10
LATENCY_PENALTY = 1000.0


def get_health(backend: str) -> str:
    with _lock:
        return _health_map.get(backend, "healthy")


def get_health_map() -> dict:
    with _lock:
        return dict(_health_map)


def is_cooled_down(backend: str) -> bool:
    with _lock:
        expire = _cooldown_cache.get(backend)
        if expire is None:
            return False
        if time.monotonic() > expire:
            del _cooldown_cache[backend]
            return False
        return True


def set_cooldown(backend: str, ttl: float = COOLDOWN_TTL):
    with _lock:
        _cooldown_cache[backend] = time.monotonic() + ttl


def get_latency_map() -> dict:
    with _lock:
        return {k: (sum(v) / len(v) if v else 1000) for k, v in _latency_windows.items()}


# ─── 被动追踪 ─────────────────────────────────────────────────────────────────

def record_success(backend: str, latency_ms: float):
    """真实请求成功后调用"""
    with _lock:
        _health_map[backend] = "healthy"
        _failure_counts[backend] = 0
        _request_counts[backend] = 0
        window = _latency_windows.setdefault(backend, [])
        if len(window) >= LATENCY_WINDOW_SIZE:
            window.pop(0)
        window.append(latency_ms)


def record_failure(backend: str, error_code: Optional[int] = None):
    """真实请求失败后调用"""
    with _lock:
        _failure_counts[backend] = _failure_counts.get(backend, 0) + 1
        _request_counts[backend] = _request_counts.get(backend, 0) + 1
        n_fail = _failure_counts[backend]
        n_total = _request_counts[backend]

        if error_code == 400:
            return  # 调用方问题，不冷却

        if error_code == 429:
            _health_map[backend] = "degraded"
            _cooldown_cache[backend] = time.monotonic() + COOLDOWN_TTL
            return

        if error_code in (401, 403):
            _health_map[backend] = "suspicious"
            return

        if n_total >= FAILURE_THRESHOLD_MIN_REQUESTS:
            fail_rate = n_fail / n_total
            if fail_rate > FAILURE_THRESHOLD_PERCENT:
                _health_map[backend] = "dead"
                return

        _health_map[backend] = "degraded"
        window = _latency_windows.setdefault(backend, [])
        if len(window) >= LATENCY_WINDOW_SIZE:
            window.pop(0)
        window.append(LATENCY_PENALTY)


# ─── 批量熔断检测 ─────────────────────────────────────────────────────────────

def detect_and_reset_mass_failure() -> bool:
    """超过 50% dead = 网络/代理问题，重置所有状态"""
    with _lock:
        if not _health_map:
            return False
        dead = sum(1 for s in _health_map.values() if s == "dead")
        if dead > len(_health_map) * 0.5:
            _health_map.clear()
            _failure_counts.clear()
            _cooldown_cache.clear()
            return True
    return False

