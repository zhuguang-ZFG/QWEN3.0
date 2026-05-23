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
    state: str = "ok"
    last_error_class: Optional[str] = None


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


def classify_failure(error_code: Optional[int] = None, error_text: str = "") -> str:
    lowered = (error_text or "").lower()
    if "anonymous_usage_exceeded" in lowered:
        return "manual_refresh_required"
    if error_code in (401, 403) or any(
        marker in lowered for marker in ("unauthorized", "forbidden", "invalid token")
    ):
        return "auth_expired"
    if error_code == 429 or any(
        marker in lowered for marker in ("too many requests", "rate limit")
    ):
        return "rate_limited"
    if any(marker in lowered for marker in ("quota", "usage exhausted", "limit exceeded")):
        return "quota_exhausted"
    if any(marker in lowered for marker in ("timeout", "timed out")):
        return "timeout"
    if error_code is not None and 500 <= error_code <= 599:
        return "provider_error"
    return "unknown_error"


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


def get_backend_state(backend: str) -> dict:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return {
                "state": "ok",
                "cooldown_until": 0.0,
                "last_error_class": None,
                "last_error_code": None,
            }
        return {
            "state": state.state,
            "cooldown_until": state.cooldown_until,
            "last_error_class": state.last_error_class,
            "last_error_code": state.last_error_code,
        }


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
            state.state = "ok"
            state.last_error_class = None

        # 记录质量
        q = _quality_states.setdefault(backend, QualityState())
        q.latencies.append(latency_ms)
        q.last_success = time.monotonic()
        q.empty_count = max(0, q.empty_count - 1)
        q.total_requests += 1


def record_failure(backend: str, error_code: Optional[int] = None,
                   error_text: str = ""):
    """Record a backend failure and classify auth/quota/rate-limit state."""
    with _lock:
        if error_code == 400:
            state = _cooldown_states.setdefault(backend, CooldownState())
            state.bad_request_count = getattr(state, 'bad_request_count', 0) + 1
            return

        state = _cooldown_states.setdefault(backend, CooldownState())
        error_class = classify_failure(error_code, error_text)
        state.consecutive_failures += 1
        state.last_error_code = error_code
        state.state = error_class
        state.last_error_class = error_class
        if error_class in ("auth_expired", "manual_refresh_required", "quota_exhausted"):
            state.current_cooldown = COOLDOWN_AUTH_FIXED
        elif error_class == "rate_limited":
            state.current_cooldown = _calc_cooldown(state.consecutive_failures, 429)
        else:
            state.current_cooldown = _calc_cooldown(
                state.consecutive_failures, error_code)
        state.cooldown_until = time.monotonic() + state.current_cooldown

        q = _quality_states.setdefault(backend, QualityState())
        q.last_failure = time.monotonic()
        q.total_requests += 1
        q.latencies.append(LATENCY_PENALTY)

        if error_class in ("auth_expired", "manual_refresh_required"):
            _health_map[backend] = "suspicious"
            return
        if error_class in ("rate_limited", "quota_exhausted"):
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


# ── P2-A: 响应质量评分 + 动态降权 ────────────────────────────────────────────

_REFUSAL_PATTERNS = [
    "i cannot", "i can't", "i apologize", "i'm sorry but i",
    "as an ai", "i'm not able to", "i don't have the ability",
    "无法为你", "抱歉，我无法", "作为AI", "我没有能力",
]

_quality_penalties: dict[str, float] = {}
_QUALITY_PENALTY_DURATION = 1800  # 30 分钟降权


def score_response_quality(response: str, query: str = "",
                           expect_code: bool = False) -> float:
    """
    评估单次响应质量，返回 0.0-1.0。
    规则评分（不需要 LLM judge）：
    - 长度合理性
    - 拒绝检测
    - 截断检测
    - 循环检测
    - 代码期望匹配
    """
    if not response or not response.strip():
        return 0.0

    score = 1.0
    text = response.strip()
    text_lower = text.lower()

    # 拒绝检测：包含拒绝模式 → 降分
    for pat in _REFUSAL_PATTERNS:
        if pat in text_lower:
            score -= 0.4
            break

    # 截断检测：末尾无标点且长度>100 → 可能被截断
    if len(text) > 100 and text[-1] not in '.!?。！？\n```':
        last_line = text.split('\n')[-1]
        if len(last_line) > 20 and last_line[-1] not in '.!?。！？}])':
            score -= 0.2

    # 循环检测：相同短语重复 3+ 次
    words = text.split()
    if len(words) > 30:
        chunks = [' '.join(words[i:i+5]) for i in range(0, len(words)-5, 5)]
        from collections import Counter
        chunk_counts = Counter(chunks)
        if chunk_counts and chunk_counts.most_common(1)[0][1] >= 3:
            score -= 0.5

    # 代码期望：问代码问题但回答没有代码块
    if expect_code and '```' not in text and 'def ' not in text and 'function' not in text:
        score -= 0.3

    # 过短回答（问题>30字但回答<20字）
    if len(query) > 30 and len(text) < 20:
        score -= 0.3

    return max(0.0, min(1.0, score))


def record_quality_score(backend: str, quality: float):
    """记录质量分数，连续低质量触发降权。"""
    with _lock:
        q = _quality_states.setdefault(backend, QualityState())
        q.total_requests += 1

        if quality < 0.4:
            q.error_msg_count += 1
            if q.error_msg_count >= 3:
                _quality_penalties[backend] = time.monotonic() + _QUALITY_PENALTY_DURATION
        else:
            q.error_msg_count = max(0, q.error_msg_count - 1)


def get_quality_penalty(backend: str) -> float:
    """返回质量降权因子 0-1。1.0=无降权，0.3=被降权。"""
    with _lock:
        deadline = _quality_penalties.get(backend, 0)
    if deadline and time.monotonic() < deadline:
        return 0.3
    return 1.0
