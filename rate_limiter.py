"""
rate_limiter.py — 滑动窗口 IP 限流
接入点: server.py 的 /v1/chat/completions 入口
"""
import time
from collections import defaultdict

WINDOW = 60
MAX_PER_WINDOW = 20

_requests: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(ip: str) -> bool:
    """返回 True 表示允许，False 表示超限。"""
    now = time.time()
    _requests[ip] = [t for t in _requests[ip] if now - t < WINDOW]
    if len(_requests[ip]) >= MAX_PER_WINDOW:
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
