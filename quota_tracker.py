"""quota_tracker.py — API 调用配额追踪，防止付费 API 费用失控。"""
import json
import os
from datetime import datetime

USAGE_FILE = "D:/GIT/data/usage.json"

# 每日硬限制（超出自动降级到免费后端）
DAILY_LIMITS = {
    "deepseek_pro":       200,
    "deepseek_pro_1m":    100,
    "claude":              50,
    "deepseek_flash":     500,
    "deepseek_flash_1m":  300,
    "longcat":            300,
    "longcat_thinking":   200,
    "longcat_chat":       300,
    # OpenRouter 免费模型（每日200次，所有 or_* 后端共享同一个 key）
    "or_deepseek_r1":      40,   # 200次/天 ÷ 5个模型，保守分配
    "or_qwen3_235b":       40,
    "or_llama70b":         60,   # 通用模型多分配一些
    "or_nemotron":         30,
    "or_qwen3_30b":        30,
}

# 超限时的免费替代后端
_FALLBACK_MAP = {
    "deepseek_pro":      "nvidia_nemotron",
    "deepseek_pro_1m":   "nvidia_nemotron",
    "claude":            "nvidia_nemotron",
    "deepseek_flash":    "nvidia_llama70b",
    "deepseek_flash_1m": "nvidia_llama70b",
    "longcat":           "nvidia_llama4",
    "longcat_thinking":  "nvidia_llama4",
    "longcat_chat":      "nvidia_llama4",
    "or_deepseek_r1":    "nvidia_nemotron",
    "or_qwen3_235b":     "nvidia_qwen_coder",
    "or_llama70b":       "nvidia_llama70b",
    "or_nemotron":       "nvidia_nemotron",
    "or_qwen3_30b":      "nvidia_llama4",
}


def _load_usage() -> dict:
    """读取 usage.json，若日期不是今天则重置计数。"""
    today = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(USAGE_FILE):
        return {"date": today, "calls": {}}
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") != today:
            # 新的一天，重置
            return {"date": today, "calls": {}}
        return data
    except Exception as e:
        print(f"[quota_tracker] 读取 usage.json 失败，重置：{e}")
        return {"date": today, "calls": {}}


def _save_usage(data: dict) -> None:
    """写回 usage.json。"""
    os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_quota(backend: str) -> bool:
    """检查后端是否还有配额。True=有配额，False=已超限。"""
    limit = DAILY_LIMITS.get(backend)
    if limit is None:
        # 不在限制列表中（如 nvidia 免费后端），不限制
        return True
    data = _load_usage()
    used = data["calls"].get(backend, 0)
    if used >= limit:
        print(
            f"[quota_tracker] {backend} 今日已用 {used}/{limit}，超限，"
            f"建议降级到 {get_fallback(backend)}"
        )
        return False
    return True


def record_call(backend: str) -> None:
    """记录一次 API 调用。"""
    data = _load_usage()
    data["calls"][backend] = data["calls"].get(backend, 0) + 1
    _save_usage(data)


def get_fallback(backend: str) -> str:
    """当 backend 超限时，返回免费替代后端。"""
    return _FALLBACK_MAP.get(backend, "nvidia_llama70b")


def get_status() -> dict:
    """返回今日所有后端的配额使用情况。"""
    data = _load_usage()
    status = {"date": data["date"], "backends": {}}
    # 已有调用记录的后端
    for backend, used in data["calls"].items():
        limit = DAILY_LIMITS.get(backend, None)
        status["backends"][backend] = {
            "used": used,
            "limit": limit if limit is not None else "unlimited",
            "remaining": (limit - used) if limit is not None else "unlimited",
        }
    # 有限制但尚未调用的后端
    for backend, limit in DAILY_LIMITS.items():
        if backend not in status["backends"]:
            status["backends"][backend] = {
                "used": 0,
                "limit": limit,
                "remaining": limit,
            }
    return status


def reset_daily() -> None:
    """重置今日计数（每天凌晨由 auto_distill_main 调用）。"""
    today = datetime.now().strftime("%Y-%m-%d")
    _save_usage({"date": today, "calls": {}})
    print(f"[quota_tracker] 已重置今日配额计数（{today}）")
