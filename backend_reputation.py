"""
backend_reputation.py — 后端信誉分系统
根据质量门结果动态调整后端优先级，低质量后端自动降级
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


def record(backend: str, passed: bool, task_type: str = "code"):
    """记录质量门结果，更新信誉分"""
    now = time.time()
    score = _scores.get(backend, INITIAL_SCORE)

    if passed:
        score = min(100, score + REWARD)
    else:
        score = max(0, score - PENALTY)
        # 检测连续失败 → 冷却
        recent = [h for h in _history[backend]
                  if h[0] > now - HISTORY_WINDOW and not h[1]]
        if len(recent) + 1 >= CONSECUTIVE_FAIL_THRESHOLD:
            _cooldowns[backend] = now + COOLDOWN_DURATION

    _scores[backend] = score
    _history[backend].append((now, passed, task_type))
    # 裁剪历史
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
        "cooldowns": {k: v - time.time() for k, v in _cooldowns.items()
                      if v > time.time()},
    }
