"""
backend_reputation.py — 后端信誉分系统
根据质量门结果和失败分类动态调整后端优先级，低质量后端自动降级。
"""

import time
from collections import defaultdict

# 信誉分: 0-100, 初始70
_scores: dict[str, float] = {}
# 历史记录: backend → [(timestamp, passed, task_type)]
_history: dict[str, list] = defaultdict(list)
# 冷却列表: backend → cooldown_until_timestamp
_cooldowns: dict[str, float] = {}

INITIAL_SCORE = 70
REWARD = 2
PENALTY = 10
CONSECUTIVE_FAIL_THRESHOLD = 3
COOLDOWN_DURATION = 1800  # 30 minutes
HISTORY_WINDOW = 600  # 10 minutes for consecutive fail detection
MAX_HISTORY = 100

# Per-error-class penalty weights (multiplier on PENALTY)
FAILURE_CLASS_PENALTY = {
    "auth_expired": 5.0,  # 立即降级
    "manual_refresh_required": 5.0,
    "quota_exhausted": 5.0,
    "rate_limited": 1.5,  # 较重惩罚
    "network_error": 0.3,  # 网络波动，轻罚
    "malformed_response": 0.5,  # 格式问题，中等
    "provider_error": 1.0,  # 默认惩罚
    "unknown_error": 0.8,
    "timeout": 0.3,  # 老分类兼容
}


def record(backend: str, passed: bool, task_type: str = "code"):
    """记录质量门结果，更新信誉分"""
    now = time.time()
    score = _scores.get(backend, INITIAL_SCORE)

    if passed:
        score = min(100, score + REWARD)
    else:
        score = max(0, score - PENALTY)
        recent = [h for h in _history[backend] if h[0] > now - HISTORY_WINDOW and not h[1]]
        if len(recent) + 1 >= CONSECUTIVE_FAIL_THRESHOLD:
            _cooldowns[backend] = now + COOLDOWN_DURATION

    _scores[backend] = score
    _history[backend].append((now, passed, task_type))
    if len(_history[backend]) > MAX_HISTORY:
        _history[backend] = _history[backend][-MAX_HISTORY:]


def record_failure_class(backend: str, error_class: str, task_type: str = "routing"):
    """Record a classified failure with weighted penalty."""
    multiplier = FAILURE_CLASS_PENALTY.get(error_class, 1.0)
    now = time.time()
    score = _scores.get(backend, INITIAL_SCORE)
    penalty = PENALTY * multiplier
    score = max(0, score - penalty)

    if multiplier >= 5.0:
        _cooldowns[backend] = now + COOLDOWN_DURATION

    _scores[backend] = score
    _history[backend].append((now, False, f"{task_type}:{error_class}"))
    if len(_history[backend]) > MAX_HISTORY:
        _history[backend] = _history[backend][-MAX_HISTORY:]


def get_score(backend: str) -> float:
    return _scores.get(backend, INITIAL_SCORE)


def is_reputation_cooled(backend: str) -> bool:
    """信誉冷却中（连续失败触发）"""
    until = _cooldowns.get(backend, 0)
    if until and time.time() < until:
        return True
    if until and time.time() >= until:
        del _cooldowns[backend]
    return False


def sort_by_reputation(pool: list[str]) -> list[str]:
    """按信誉分降序排列后端池，排除冷却中的"""
    available = [b for b in pool if not is_reputation_cooled(b)]
    return sorted(available, key=lambda b: -get_score(b))


def get_stats() -> dict:
    """返回当前信誉状态（调试用）"""
    return {
        "scores": dict(_scores),
        "cooldowns": {k: v - time.time() for k, v in _cooldowns.items() if v > time.time()},
    }
