"""
LiMa Health Tracker v2 — 指数退避 + 响应质量追踪 + 健康评分

升级自 v1 (固定 5s cooldown):
- 指数退避: 5s → 10s → 20s → ... → 300s(cap)，成功即重置
- 质量追踪: 响应长度、空响应率、错误消息率、延迟突增
- 健康评分: 0-100 连续分数，供加权路由使用
- 接口兼容: is_cooled_down, record_success, record_failure, get_health_map 签名不变
"""

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

# ─── 退避参数 ────────────────────────────────────────────────────────────────

BASE_COOLDOWN = 5
MAX_COOLDOWN = 300
BACKOFF_FACTOR = 2
COOLDOWN_429_BASE = 30
COOLDOWN_AUTH_FIXED = 300

# ─── 质量追踪参数 ─────────────────────────────────────────────────────────────

QUALITY_WINDOW = 50
LATENCY_WINDOW_SIZE = 20
LATENCY_PENALTY = 5000.0
FAILURE_THRESHOLD_PERCENT = 0.5
FAILURE_THRESHOLD_MIN_REQUESTS = 5

# ─── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class CooldownState:
    consecutive_failures: int = 0
    current_cooldown: float = BASE_COOLDOWN
    cooldown_until: float = 0.0
    last_error_code: Optional[int] = None


@dataclass
class QualityState:
    response_lengths: deque = field(default_factory=lambda: deque(maxlen=QUALITY_WINDOW))
    latencies: deque = field(default_factory=lambda: deque(maxlen=LATENCY_WINDOW_SIZE))
    empty_count: int = 0
    error_msg_count: int = 0
    total_requests: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0


# ─── 全局状态 ────────────────────────────────────────────────────────────────

_lock = threading.RLock()
_health_map: dict[str, str] = {}
_cooldown_states: dict[str, CooldownState] = {}
_quality_states: dict[str, QualityState] = {}


# ─── Cooldown 计算 ───────────────────────────────────────────────────────────

def _calc_cooldown(failures: int, error_code: Optional[int] = None) -> float:
    """计算退避时间。429 起步更高，401/403 直接最大值。"""
    if error_code in (401, 403):
        return COOLDOWN_AUTH_FIXED
    base = COOLDOWN_429_BASE if error_code == 429 else BASE_COOLDOWN
    cooldown = base * (BACKOFF_FACTOR ** (failures - 1))
    return min(cooldown, MAX_COOLDOWN)


# ─── 公开接口（兼容 v1）────────────────────────────────────────────────────────

def get_health(backend: str) -> str:
    with _lock:
        return _health_map.get(backend, "healthy")


def get_health_map() -> dict:
    with _lock:
        return dict(_health_map)


def is_cooled_down(backend: str) -> bool:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return False
        if time.monotonic() > state.cooldown_until:
            return False
        return True


def set_cooldown(backend: str, ttl: float = BASE_COOLDOWN):
    """手动设置冷却（兼容旧调用）。"""
    with _lock:
        state = _cooldown_states.setdefault(backend, CooldownState())
        state.cooldown_until = time.monotonic() + ttl


def get_cooldown_remaining(backend: str) -> float:
    """剩余冷却秒数（调试/监控用）。"""
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return 0.0
        return max(0, state.cooldown_until - time.monotonic())


def get_latency_map() -> dict:
    with _lock:
        result = {}
        for k, q in _quality_states.items():
            if q.latencies:
                result[k] = sum(q.latencies) / len(q.latencies)
            else:
                result[k] = 1000.0
        return result


# ─── 被动追踪 ────────────────────────────────────────────────────────────────

def record_success(backend: str, latency_ms: float):
    """真实请求成功后调用。重置退避，记录质量数据。"""
    with _lock:
        _health_map[backend] = "healthy"

        # 重置退避（含 cooldown_until）
        state = _cooldown_states.get(backend)
        if state:
            state.consecutive_failures = 0
            state.current_cooldown = BASE_COOLDOWN
            state.cooldown_until = 0.0

        # 记录质量
        q = _quality_states.setdefault(backend, QualityState())
        q.latencies.append(latency_ms)
        q.last_success = time.monotonic()
        q.empty_count = 0
        q.total_requests += 1


def record_failure(backend: str, error_code: Optional[int] = None):
    """真实请求失败后调用。指数退避 + 更新健康状态。"""
    with _lock:
        if error_code == 400:
            return

        # 更新退避状态
        state = _cooldown_states.setdefault(backend, CooldownState())
        state.consecutive_failures += 1
        state.last_error_code = error_code
        state.current_cooldown = _calc_cooldown(
            state.consecutive_failures, error_code)
        state.cooldown_until = time.monotonic() + state.current_cooldown

        # 更新质量状态
        q = _quality_states.setdefault(backend, QualityState())
        q.last_failure = time.monotonic()
        q.total_requests += 1
        q.latencies.append(LATENCY_PENALTY)

        # 更新健康状态
        if error_code in (401, 403):
            _health_map[backend] = "suspicious"
            return
        if error_code == 429:
            _health_map[backend] = "degraded"
            return

        n_fail = state.consecutive_failures
        if n_fail >= FAILURE_THRESHOLD_MIN_REQUESTS:
            _health_map[backend] = "dead"
        else:
            _health_map[backend] = "degraded"


def record_response_quality(backend: str, response_length: int,
                            is_error_msg: bool = False):
    """记录响应质量数据（由 http_caller 在成功后调用）。"""
    with _lock:
        q = _quality_states.setdefault(backend, QualityState())
        q.response_lengths.append(response_length)
        if response_length == 0:
            q.empty_count += 1
        else:
            q.empty_count = 0
        if is_error_msg:
            q.error_msg_count += 1


# ─── 健康评分 ────────────────────────────────────────────────────────────────

def compute_score(backend: str) -> float:
    """0-100 分。成功率(50) + 延迟(30) + 新鲜度(20)。"""
    with _lock:
        q = _quality_states.get(backend)
        if not q or q.total_requests == 0:
            return 50.0

        # 成功率: 基于连续失败次数
        state = _cooldown_states.get(backend)
        failures = state.consecutive_failures if state else 0
        success_factor = max(0, 1.0 - failures * 0.2)

        # 延迟: 归一化到 0-1 (5s = 最差)
        if q.latencies:
            avg_lat = sum(q.latencies) / len(q.latencies)
            latency_factor = 1.0 - min(avg_lat / 5000, 1.0)
        else:
            latency_factor = 0.5

        # 新鲜度: 5分钟内有成功 = 满分
        if q.last_success > 0:
            age = time.monotonic() - q.last_success
            recency_factor = 1.0 - min(age / 300, 1.0)
        else:
            recency_factor = 0.0

        score = (
            success_factor * 50 +
            latency_factor * 30 +
            recency_factor * 20
        )
        return round(max(0, min(100, score)), 1)


def get_scores() -> dict[str, float]:
    """返回所有后端的健康评分。"""
    with _lock:
        backends = set(list(_health_map.keys()) + list(_quality_states.keys()))
    return {b: compute_score(b) for b in backends}


# ─── 质量降级检测 ─────────────────────────────────────────────────────────────

def detect_degradation(backend: str) -> str:
    """返回: 'healthy' | 'degraded' | 'dead'"""
    with _lock:
        q = _quality_states.get(backend)
        if not q:
            return "healthy"

        if q.empty_count >= 3:
            return "dead"

        if q.total_requests >= 5 and q.error_msg_count > q.total_requests * 0.5:
            return "dead"

        if len(q.response_lengths) >= 10:
            recent = list(q.response_lengths)[-5:]
            historical = list(q.response_lengths)
            recent_avg = sum(recent) / len(recent) if recent else 0
            hist_avg = sum(historical) / len(historical) if historical else 1
            if hist_avg > 0 and recent_avg < hist_avg * 0.3:
                return "degraded"

        return "healthy"


# ─── 批量熔断检测 ─────────────────────────────────────────────────────────────

def detect_and_reset_mass_failure() -> bool:
    """超过 50% dead = 网络/代理问题，重置所有状态。"""
    with _lock:
        if not _health_map:
            return False
        dead = sum(1 for s in _health_map.values() if s == "dead")
        if dead > len(_health_map) * 0.5:
            _health_map.clear()
            _cooldown_states.clear()
            _quality_states.clear()
            return True
    return False


# ─── 调试/监控 ────────────────────────────────────────────────────────────────

def get_backend_status(backend: str) -> dict:
    """返回单个后端的完整状态（供 /debug 接口使用）。"""
    with _lock:
        state = _cooldown_states.get(backend)
        q = _quality_states.get(backend)
        return {
            "health": _health_map.get(backend, "healthy"),
            "score": compute_score(backend),
            "cooldown_remaining": max(0, state.cooldown_until - time.monotonic()) if state else 0,
            "consecutive_failures": state.consecutive_failures if state else 0,
            "current_cooldown_s": state.current_cooldown if state else BASE_COOLDOWN,
            "last_error_code": state.last_error_code if state else None,
            "avg_latency_ms": (sum(q.latencies) / len(q.latencies)) if q and q.latencies else None,
            "total_requests": q.total_requests if q else 0,
            "empty_count": q.empty_count if q else 0,
            "error_msg_count": q.error_msg_count if q else 0,
        }
