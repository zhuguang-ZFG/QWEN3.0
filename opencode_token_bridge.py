"""opencode_token_bridge.py — Token 精度桥接与溢出预测。

直接对接 OpenCode 的 overflow.ts 和 token.ts 源码逻辑，
在 LiMa 侧提供精确 token 计数，帮助 OpenCode 更早触发 compaction。

核心功能:
  1. estimate_accurate_tokens() — 基于 API usage 的精确 token 计数
  2. predict_overflow_after_n_turns() — 预估溢出轮次
  3. build_overflow_early_warning() — 提前注入压缩提示
  4. inject_token_budget_info() — 注入剩余 token 预算
  5. build_compaction_hint_header() — x-lima-compaction-hint header

源码参考:
  - opencode-source/packages/opencode/src/session/overflow.ts (usable/isOverflow)
  - opencode-source/packages/opencode/src/util/token.ts (chars/4 estimate)
  - opencode-source/packages/opencode/src/session/compaction.ts (COMPACTION_BUFFER=20000)
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# ── OpenCode 源码常量 ─────────────────────────────────────────────────────
# From overflow.ts: COMPACTION_BUFFER = 20_000
COMPACTION_BUFFER = 20_000
# From token.ts: CHARS_PER_TOKEN = 4
CHARS_PER_TOKEN = 4
# From compaction.ts: PRUNE_MINIMUM = 20_000, PRUNE_PROTECT = 40_000
PRUNE_MINIMUM = 20_000
PRUNE_PROTECT = 40_000

# ── 后端上下文窗口大小 ────────────────────────────────────────────────────
# input limit = 总上下文 - maxOutputTokens; 这里记录总上下文窗口
_BACKEND_CONTEXT_WINDOW: dict[str, int] = {
    # OpenAI
    "github_gpt4o": 128_000, "github_gpt4o_mini": 128_000,
    # Anthropic
    "github_claude_sonnet4": 200_000, "github_claude_haiku35": 200_000,
    # SCNet DeepSeek
    "scnet_ds_flash": 128_000, "scnet_ds_pro": 128_000,
    "scnet_large_ds_flash": 128_000, "scnet_large_ds_pro": 128_000,
    # SCNet Qwen
    "scnet_qwen30b": 32_000, "scnet_qwen235b": 32_000,
    # Cloudflare
    "cf_qwen_coder": 32_000, "cfai_qwen_coder": 32_000,
    "cf_deepseek_r1": 32_000, "cfai_deepseek_r1": 32_000,
    "cf_gptoss_120b": 32_000, "cfai_llama70b": 32_000,
    "cf_qwen3_30b": 32_000, "cf_llama70b": 32_000,
    "cf_mistral": 32_000, "cf_kimi_k26": 32_000,
    # Groq
    "groq_llama70b": 128_000, "groq_gptoss": 128_000,
    "groq_gptoss_20b": 128_000, "groq_qwen32b": 128_000,
    "groq_llama4": 128_000,
    # Cerebras
    "cerebras_gptoss": 128_000,
    # Mistral
    "mistral_large": 128_000, "mistral_small": 32_000,
    "mistral_codestral": 32_000, "mistral_devstral": 32_000,
    # NVIDIA
    "nvidia_qwen_coder": 32_000, "nvidia_qwen35_coder": 128_000,
    "nvidia_deepseek_v4": 128_000,
    # Google
    "google_flash": 1_048_576, "google_flash_lite": 1_048_576,
    "google_pro": 2_097_152,
    # OpenRouter
    "or_gptoss_120b": 128_000, "or_qwen3_coder": 32_000,
    # Kimi
    "kimi": 128_000,
    # DeepInfra
    "deepinfra_qwen235b": 32_000, "deepinfra_llama4": 128_000,
    # Fireworks
    "fireworks_llama405b": 128_000,
    # SambaNova
    "sambanova_ds_v3": 128_000, "sambanova_llama4": 128_000,
    # GitHub Models
    "github_codestral": 32_000, "github_deepseek_r1": 128_000,
    "github_llama70b": 128_000,
    # Default conservative
    "default": 16_384,
}

# 默认最大输出 token（用于计算 usable 时扣减）
_DEFAULT_MAX_OUTPUT_TOKENS = 4096


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for mixed text."""
    return max(1, len(text or "") // CHARS_PER_TOKEN)


def get_context_window(backend: str) -> int:
    """获取后端的总上下文窗口大小（token 数）。"""
    return _BACKEND_CONTEXT_WINDOW.get(backend, _BACKEND_CONTEXT_WINDOW["default"])


def estimate_max_output(backend: str) -> int:
    """估算后端最大输出 token 数。"""
    lower = backend.lower()
    if any(k in lower for k in ("coder", "codestral", "gpt-4", "claude", "gemini-2", "deepseek")):
        return 16384
    if any(k in lower for k in ("qwen", "llama", "mistral")):
        return 8192
    return _DEFAULT_MAX_OUTPUT_TOKENS


# ── 核心: 复刻 OpenCode overflow.ts 的 usable() 逻辑 ───────────────────────

def compute_usable_tokens(backend: str, max_output: int | None = None) -> int:
    """计算 OpenCode 实际可用的输入 token 数。

    复刻 overflow.ts 的 usable() 函数:
      usable = max(0, context_window - reserved)
      reserved = min(COMPACTION_BUFFER, maxOutputTokens)

    Returns:
        可用输入 token 数。0 表示无法确定上下文窗口。
    """
    context = get_context_window(backend)
    if context <= 0:
        return 0
    output = max_output if max_output else estimate_max_output(backend)
    reserved = min(COMPACTION_BUFFER, output)
    return max(0, context - reserved)


# ── 精确 token 计数 ────────────────────────────────────────────────────────

def estimate_accurate_tokens(
    messages: list[dict],
    usage: dict | None = None,
    system_prompt: str = "",
) -> int:
    """基于 API usage 和内容估算精确 token 数。

    优先使用 API 返回的 usage.prompt_tokens，回退到 chars/4 估算。

    Args:
        messages: 消息列表。
        usage: API 返回的 usage 对象（如 {"prompt_tokens": 1500, ...}）。
        system_prompt: 系统提示。

    Returns:
        预估的 prompt token 数。
    """
    if usage and isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens")
        if isinstance(prompt_tokens, (int, float)) and prompt_tokens > 0:
            return int(prompt_tokens)

    # Fallback: chars/4 estimation
    total = estimate_tokens(system_prompt)
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text", "") or block.get("content", "") or ""
                    total += estimate_tokens(str(text))
        # Tool calls
        tool_calls = m.get("tool_calls") or []
        for tc in tool_calls:
            if isinstance(tc, dict):
                fn = tc.get("function", {})
                total += estimate_tokens(
                    str(fn.get("name", "")) + str(fn.get("arguments", ""))
                )

    return total


def compute_usage_percentage(
    messages: list[dict],
    backend: str,
    usage: dict | None = None,
    system_prompt: str = "",
    max_output: int | None = None,
) -> dict[str, Any]:
    """计算当前上下文使用百分比及相关指标。

    Returns:
        {
            "prompt_tokens": int,         # 当前 prompt token 数
            "usable_tokens": int,         # 可用输入 token 数
            "context_window": int,        # 总上下文窗口
            "usage_percent": float,       # 使用百分比 (0-100)
            "is_near_overflow": bool,     # 是否接近溢出 (>85%)
            "estimated_turns_left": int,  # 估算剩余轮次
            "compaction_recommended": bool,  # 是否建议压缩
        }
    """
    prompt_tokens = estimate_accurate_tokens(messages, usage, system_prompt)
    context = get_context_window(backend)
    output = max_output if max_output else estimate_max_output(backend)
    reserved = min(COMPACTION_BUFFER, output)
    usable = max(0, context - reserved)

    if usable <= 0:
        return {
            "prompt_tokens": prompt_tokens,
            "usable_tokens": 0,
            "context_window": context,
            "usage_percent": 100.0,
            "is_near_overflow": True,
            "estimated_turns_left": 0,
            "compaction_recommended": True,
        }

    usage_percent = min(100.0, (prompt_tokens / usable) * 100)

    # 估算每轮平均 token 消耗
    avg_turn_tokens = 3000  # 保守估计：user+assistant+tool_results per turn
    is_near = usage_percent > 85.0
    remaining = max(0, usable - prompt_tokens)
    turns_left = max(0, remaining // avg_turn_tokens)

    return {
        "prompt_tokens": prompt_tokens,
        "usable_tokens": usable,
        "context_window": context,
        "usage_percent": round(usage_percent, 1),
        "is_near_overflow": is_near,
        "estimated_turns_left": turns_left,
        "compaction_recommended": usage_percent > 70.0,
    }


# ── 溢出预测 ───────────────────────────────────────────────────────────────

def predict_overflow_after_n_turns(
    messages: list[dict],
    n_turns: int,
    backend: str,
    usage: dict | None = None,
    system_prompt: str = "",
    avg_turn_tokens: int = 3000,
) -> dict[str, Any]:
    """预估在 N 轮工具调用后是否会溢出。

    Args:
        messages: 当前消息列表。
        n_turns: 预测的轮次数。
        backend: 后端名称。
        usage: 当前 usage 信息。
        system_prompt: 系统提示。
        avg_turn_tokens: 每轮平均消耗 token 数。

    Returns:
        {"will_overflow": bool, "projected_tokens": int, "usable": int, "turns_before_overflow": int}
    """
    current = estimate_accurate_tokens(messages, usage, system_prompt)
    usable = compute_usable_tokens(backend)
    projected = current + (n_turns * avg_turn_tokens)
    will_overflow = projected >= usable
    remaining = max(0, usable - current)
    turns_before = max(0, remaining // max(1, avg_turn_tokens)) if avg_turn_tokens > 0 else 0

    return {
        "will_overflow": will_overflow,
        "projected_tokens": projected,
        "usable": usable,
        "current_tokens": current,
        "turns_before_overflow": turns_before,
    }


# ── 上下文预算注入 ─────────────────────────────────────────────────────────

def inject_token_budget_info(
    messages: list[dict],
    backend: str,
    usage: dict | None = None,
    system_prompt: str = "",
) -> list[dict]:
    """在 system prompt 注入剩余 token 预算信息。

    让弱后端知道上下文即将满载，从而自觉精简输出。

    Args:
        messages: 消息列表。
        backend: 后端名称。
        usage: 当前 usage。
        system_prompt: 系统提示。

    Returns:
        注入后的消息列表。
    """
    stats = compute_usage_percentage(messages, backend, usage, system_prompt)

    if not stats["is_near_overflow"]:
        return list(messages)

    hint = _build_budget_hint(stats)

    result = list(messages)
    # Find system message to append
    for i, msg in enumerate(result):
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                result[i] = {**msg, "content": content.rstrip() + "\n" + hint}
            elif isinstance(content, list):
                result[i] = {
                    **msg,
                    "content": content + [{"type": "text", "text": hint}],
                }
            return result

    # No system message, insert at beginning
    result.insert(0, {"role": "system", "content": hint})
    return result


def _build_budget_hint(stats: dict) -> str:
    """Build a concise token budget hint for the model."""
    percent = stats["usage_percent"]
    turns = stats["estimated_turns_left"]

    lines = [
        "\n## ⚠️ Context Budget Warning",
        f"- Current context usage: {percent:.0f}% of available input tokens.",
        f"- Only ~{turns} more tool-call turns can fit before context overflow.",
        "- Be concise in your responses. Avoid unnecessary explanations.",
        "- Prioritize the most critical tool calls first.",
        "- Return complete, working code — do NOT use TODO, pass, or stubs.",
    ]

    if percent > 90:
        lines.append(
            "- CRITICAL: Very close to context limit. Use minimal output. "
            "If you need to read a file, use the smallest possible scope."
        )

    return "\n".join(lines)


# ── 压缩提示 header ───────────────────────────────────────────────────────

def build_compaction_hint_header(
    messages: list[dict],
    backend: str,
    usage: dict | None = None,
    system_prompt: str = "",
) -> dict[str, str]:
    """生成 x-lima-compaction-hint header。

    OpenCode 可以通过这个 header 提前知道是否需要触发 compaction。

    Returns:
        Header dict 如 {"x-lima-compaction-hint": "recommended"}。
    """
    stats = compute_usage_percentage(messages, backend, usage, system_prompt)

    if stats["compaction_recommended"] and stats["usage_percent"] > 85:
        return {
            "x-lima-compaction-hint": "critical",
            "x-lima-token-usage-percent": str(stats["usage_percent"]),
            "x-lima-token-usable": str(stats["usable_tokens"]),
            "x-lima-token-current": str(stats["prompt_tokens"]),
        }

    if stats["compaction_recommended"]:
        return {
            "x-lima-compaction-hint": "recommended",
            "x-lima-token-usage-percent": str(stats["usage_percent"]),
        }

    return {
        "x-lima-compaction-hint": "ok",
        "x-lima-token-usage-percent": str(stats["usage_percent"]),
    }


# ── 溢出提前警告 ───────────────────────────────────────────────────────────

def build_overflow_early_warning(
    messages: list[dict],
    backend: str,
    usage: dict | None = None,
    system_prompt: str = "",
) -> str:
    """构建溢出提前警告文本。

    可在 system prompt 中注入此文本以告知模型上下文即将满载。

    Returns:
        警告文本字符串，若不必要则为空字符串。
    """
    stats = compute_usage_percentage(messages, backend, usage, system_prompt)

    if not stats["compaction_recommended"]:
        return ""

    return _build_budget_hint(stats)


# ── Usage 增强 (用于 x-lima-usage header) ─────────────────────────────────

def enrich_usage_for_opencode(
    usage: dict | None,
    messages: list[dict] | None = None,
    backend: str = "",
    system_prompt: str = "",
) -> dict:
    """增强 usage 信息供 OpenCode 读取。

    OpenCode 通过 x-lima-usage header 读取 token 信息。
    增强字段帮助 OpenCode 的 compaction/overflow 判断。

    Args:
        usage: 原始 usage dict。
        messages: 当前消息列表（可选，用于补充估算）。
        backend: 后端名称。
        system_prompt: 系统提示。

    Returns:
        增强后的 usage dict。
    """
    result = dict(usage) if usage else {}

    # 如果 API 没有返回 usage，基于消息估算
    if messages and "prompt_tokens" not in result:
        result["prompt_tokens"] = estimate_accurate_tokens(
            messages, None, system_prompt,
        )

    # 添加 OpenCode 需要的 compaction 相关字段
    if backend:
        usable = compute_usable_tokens(backend)
        if usable > 0:
            prompt = result.get("prompt_tokens", 0)
            result["openCode_usable_input"] = usable
            result["openCode_usage_ratio"] = round(
                min(1.0, prompt / usable) if usable else 0, 3,
            )

    return result
