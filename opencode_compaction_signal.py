"""opencode_compaction_signal.py — 上下文压缩信号生成与检测。

复刻 OpenCode session/overflow.ts + session/compaction.ts 的 compaction 触发逻辑。

OpenCode 的 compaction 触发条件 (overflow.ts):
- tokens.total >= usable_tokens (context - output_reserve)
- usable = context - maxOutputTokens (默认 20K buffer)
- compaction.auto === false 时禁用
- 触发后返回 "compact" 信号让客户端执行压缩

LiMa 服务端可以:
1. 检测 token 使用量接近上限时，在响应中注入 compaction 信号
2. 通过 x-lima-compaction-hint header 或特殊 finish_reason 告知客户端
3. 提供 overflow 预警，让客户端提前处理

compaction 选择策略 (compaction.ts):
- PRUNE_MINIMUM = 20000 (最小裁剪 token 数)
- PRUNE_PROTECT = 40000 (保护最新的 N tokens 不被裁剪)
- tail_turns: 保留最后 N 轮完整对话

源码参考:
  - opencode-source/packages/opencode/src/session/overflow.ts
  - opencode-source/packages/opencode/src/session/compaction.ts
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# ── OpenCode 源码常量 ─────────────────────────────────────────────────────
# overflow.ts: COMPACTION_BUFFER = 20_000
COMPACTION_BUFFER = 20_000
# compaction.ts: PRUNE_MINIMUM = 20_000, PRUNE_PROTECT = 40_000
PRUNE_MINIMUM = 20_000
PRUNE_PROTECT = 40_000
# 压缩触发的安全阈值 (usage_percent)
COMPACTION_WARNING_THRESHOLD = 70.0
COMPACTION_CRITICAL_THRESHOLD = 85.0
COMPACTION_TRIGGER_THRESHOLD = 95.0


# ── Compaction 信号类型 ────────────────────────────────────────────────────
SIGNAL_OK = "ok"
SIGNAL_WARNING = "warning"
SIGNAL_CRITICAL = "critical"
SIGNAL_COMPACT = "compact"


def compute_usable(context_window: int, max_output_tokens: int | None = None) -> int:
    """计算可用输入 token 数。

    复刻 overflow.ts usable() 函数:
      reserved = maxOutputTokens ? min(COMPACTION_BUFFER, maxOutputTokens) : COMPACTION_BUFFER
      usable = max(0, context_window - reserved)

    Args:
        context_window: 模型总上下文窗口大小。
        max_output_tokens: 最大输出 token 数 (可选)。

    Returns:
        可用输入 token 数。
    """
    if context_window <= 0:
        return 0
    if max_output_tokens and max_output_tokens > 0:
        reserved = min(COMPACTION_BUFFER, max_output_tokens)
    else:
        reserved = COMPACTION_BUFFER
    return max(0, context_window - reserved)


def is_overflow(total_tokens: int, usable_tokens: int) -> bool:
    """检测是否已溢出。

    复刻 overflow.ts isOverflow():
      return tokens.total >= usable

    Args:
        total_tokens: 当前总 token 使用量。
        usable_tokens: 可用 token 数。

    Returns:
        True 表示已溢出或即将溢出。
    """
    if usable_tokens <= 0:
        return False
    return total_tokens >= usable_tokens


def evaluate_compaction_signal(
    total_tokens: int,
    context_window: int,
    max_output_tokens: int | None = None,
    auto_compaction: bool = True,
) -> dict[str, Any]:
    """评估是否需要触发 compaction，返回信号详情。

    综合 overflow.ts isOverflow() + compaction.ts 逻辑:
    1. 计算 usable tokens
    2. 计算使用百分比
    3. 根据阈值返回信号级别

    Args:
        total_tokens: 当前总 token 使用量 (prompt_tokens)。
        context_window: 模型总上下文窗口。
        max_output_tokens: 最大输出 token 数。
        auto_compaction: 是否启用自动压缩 (compaction.auto)。

    Returns:
        {
            "signal": "ok" | "warning" | "critical" | "compact",
            "usage_percent": float,
            "usable_tokens": int,
            "total_tokens": int,
            "should_compact": bool,
            "auto_disabled": bool,
            "prune_recommendation": {
                "prune_tokens": int,       # 建议裁剪的 token 数
                "protect_tokens": int,     # 保护不被裁剪的 token 数
            },
        }
    """
    usable = compute_usable(context_window, max_output_tokens)

    if usable <= 0:
        return {
            "signal": SIGNAL_COMPACT,
            "usage_percent": 100.0,
            "usable_tokens": 0,
            "total_tokens": total_tokens,
            "should_compact": True,
            "auto_disabled": not auto_compaction,
            "prune_recommendation": _compute_prune(total_tokens),
        }

    usage_pct = min(100.0, (total_tokens / usable) * 100)

    # 判定信号级别
    if usage_pct >= COMPACTION_TRIGGER_THRESHOLD:
        signal = SIGNAL_COMPACT
        should_compact = True
    elif usage_pct >= COMPACTION_CRITICAL_THRESHOLD:
        signal = SIGNAL_CRITICAL
        should_compact = auto_compaction
    elif usage_pct >= COMPACTION_WARNING_THRESHOLD:
        signal = SIGNAL_WARNING
        should_compact = False
    else:
        signal = SIGNAL_OK
        should_compact = False

    # 如果 auto_compaction 禁用且达到 critical/compact，建议压缩
    if not auto_compaction and signal in (SIGNAL_CRITICAL, SIGNAL_COMPACT):
        should_compact = False

    return {
        "signal": signal,
        "usage_percent": round(usage_pct, 1),
        "usable_tokens": usable,
        "total_tokens": total_tokens,
        "should_compact": should_compact,
        "auto_disabled": not auto_compaction,
        "prune_recommendation": _compute_prune(total_tokens) if should_compact else None,
    }


def _compute_prune(total_tokens: int) -> dict[str, int]:
    """计算裁剪建议 (compaction.ts select 逻辑)。

    PRUNE_MINIMUM = 20000: 每次至少裁剪 20K tokens
    PRUNE_PROTECT = 40000: 保护最新的 40K tokens 不被裁剪

    Returns:
        {"prune_tokens": int, "protect_tokens": int}
    """
    # 裁剪量 = max(PRUNE_MINIMUM, total - PRUNE_PROTECT)
    prune = max(PRUNE_MINIMUM, total_tokens - PRUNE_PROTECT)
    return {
        "prune_tokens": prune,
        "protect_tokens": PRUNE_PROTECT,
    }


def build_compaction_response_headers(
    signal_result: dict[str, Any],
) -> dict[str, str]:
    """构建 compaction 信号响应头。

    通过 HTTP 响应头告知 OpenCode 客户端需要压缩。

    Args:
        signal_result: evaluate_compaction_signal() 的返回值。

    Returns:
        响应头字典。
    """
    headers: dict[str, str] = {
        "x-lima-compaction-hint": signal_result["signal"],
        "x-lima-token-usage-percent": str(signal_result["usage_percent"]),
        "x-lima-token-usable": str(signal_result["usable_tokens"]),
        "x-lima-token-current": str(signal_result["total_tokens"]),
    }

    if signal_result["should_compact"]:
        headers["x-lima-should-compact"] = "true"
        prune = signal_result.get("prune_recommendation")
        if prune:
            headers["x-lima-prune-tokens"] = str(prune["prune_tokens"])
            headers["x-lima-protect-tokens"] = str(prune["protect_tokens"])

    return headers


def inject_compaction_signal_in_response(
    response_body: dict,
    signal_result: dict[str, Any],
) -> dict:
    """在响应体中注入 compaction 信号。

    在 OpenAI 格式的响应中添加 compaction 信息，让 OpenCode 客户端
    可以从响应体中读取（备选方案，当 headers 不可用时）。

    Args:
        response_body: 原始响应体 dict。
        signal_result: evaluate_compaction_signal() 返回值。

    Returns:
        注入后的响应体。
    """
    if signal_result["signal"] == SIGNAL_OK:
        return response_body

    result = dict(response_body)
    result["_lima_compaction"] = {
        "signal": signal_result["signal"],
        "usage_percent": signal_result["usage_percent"],
        "should_compact": signal_result["should_compact"],
    }

    return result


def should_trigger_compaction(
    messages: list[dict],
    backend: str,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
    usage: dict | None = None,
) -> bool:
    """便捷方法: 判断当前会话是否应触发 compaction。

    集成 overflow.ts + token_bridge 的完整检测链:
    1. 估算当前 token 使用量
    2. 获取后端上下文窗口
    3. 调用 evaluate_compaction_signal()

    Args:
        messages: 当前消息列表。
        backend: 后端名称。
        context_window: 上下文窗口 (可选，从 backend 推断)。
        max_output_tokens: 最大输出 token (可选)。
        usage: API 返回的 usage 信息 (可选)。

    Returns:
        True 表示应触发 compaction。
    """
    from opencode_token_bridge import (
        estimate_accurate_tokens,
        estimate_max_output,
        get_context_window,
    )

    total = estimate_accurate_tokens(messages, usage)
    ctx_window = context_window or get_context_window(backend)
    max_out = max_output_tokens or estimate_max_output(backend)

    result = evaluate_compaction_signal(total, ctx_window, max_out)
    return result["should_compact"]
