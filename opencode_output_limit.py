"""opencode_output_limit.py — Max Output Tokens 封顶逻辑。

复刻 OpenCode provider/transform.ts 的 OUTPUT_TOKEN_MAX (L18, L1250-1252)。

OpenCode 对所有模型的 max_output_tokens 做统一封顶:
  OUTPUT_TOKEN_MAX = 32_000
  maxTokens = Math.min(model.limit.output, OUTPUT_TOKEN_MAX) || OUTPUT_TOKEN_MAX

不同后端报告的 limit.output 差异巨大 (8192 ~ 128000)，
不封顶会导致后端过度分配 token 预算和成本浪费。

源码参考:
  - opencode-source/packages/opencode/src/provider/transform.ts (L18, L1250-1252)
"""

from __future__ import annotations

import logging
import re
from typing import Any

_log = logging.getLogger(__name__)

# ── OpenCode 源码常量 (transform.ts:18) ────────────────────────────────────
OUTPUT_TOKEN_MAX = 32_000

# ── 后端特定输出上限 ────────────────────────────────────────────────────────
# 某些后端有自己的硬限制，低于 OUTPUT_TOKEN_MAX
_BACKEND_OUTPUT_LIMITS: dict[str, int] = {
    # 小型后端
    "cf_qwen_coder": 8_192,
    "cfai_qwen_coder": 8_192,
    "cf_qwen3_30b": 8_192,
    "cf_llama70b": 8_192,
    "cfai_llama70b": 8_192,
    "cf_gptoss_120b": 8_192,
    "cfai_gptoss_120b": 8_192,
    "cf_mistral": 8_192,
    "cf_kimi_k26": 8_192,
    "cf_deepseek_r1": 16_384,
    "cfai_deepseek_r1": 16_384,
    # SCNet
    "scnet_qwen30b": 8_192,
    "scnet_qwen235b": 8_192,
    "scnet_ds_flash": 16_384,
    "scnet_ds_pro": 16_384,
    "scnet_large_ds_flash": 16_384,
    "scnet_large_ds_pro": 16_384,
    # Cloudflare
    "cf_deepseek_r1": 16_384,
    # Default
    "default": OUTPUT_TOKEN_MAX,
}

# ── 模型族输出上限 (某些模型族有更高的自然上限) ──────────────────────────────
_MODEL_FAMILY_LIMITS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"o[134]", re.IGNORECASE), 100_000),     # OpenAI o-series 推理模型
    (re.compile(r"gpt-?5", re.IGNORECASE), 64_000),      # GPT-5 系列
    (re.compile(r"claude", re.IGNORECASE), 16_384),       # Anthropic (一般)
    (re.compile(r"claude.*opus", re.IGNORECASE), 32_000), # Claude Opus 支持更高
    (re.compile(r"gemini.*pro", re.IGNORECASE), 65_536),  # Gemini Pro
    (re.compile(r"gemini.*flash", re.IGNORECASE), 65_536),# Gemini Flash
    (re.compile(r"deepseek", re.IGNORECASE), 16_384),     # DeepSeek
]


def resolve_max_output_tokens(
    requested_max: int | None = None,
    model_limit: int | None = None,
    backend_name: str = "",
    model_id: str = "",
) -> int:
    """计算最终的 max_output_tokens 值。

    复刻 transform.ts L1250-1252:
      maxTokens = Math.min(model.limit.output, OUTPUT_TOKEN_MAX) || OUTPUT_TOKEN_MAX

    优先级:
    1. 后端特定硬限制 (最低优先)
    2. 模型族自然上限
    3. OUTPUT_TOKEN_MAX 全局封顶
    4. 客户端请求的 max_tokens (如果低于上述限制)

    Args:
        requested_max: 客户端请求的 max_tokens (可能为 None)。
        model_limit: 模型报告的 limit.output (可能为 None)。
        backend_name: 后端名称。
        model_id: 模型标识符。

    Returns:
        最终使用的 max_output_tokens 值。
    """
    # 确定有效上限
    effective_cap = OUTPUT_TOKEN_MAX

    # 后端特定限制
    backend_limit = _BACKEND_OUTPUT_LIMITS.get(backend_name)
    if backend_limit and backend_limit < effective_cap:
        effective_cap = backend_limit

    # 模型族限制
    if model_id:
        for pattern, limit in _MODEL_FAMILY_LIMITS:
            if pattern.search(model_id):
                if limit < effective_cap:
                    effective_cap = limit
                break

    # 模型报告的 limit
    if model_limit and model_limit > 0:
        effective_cap = min(effective_cap, model_limit)

    # 客户端请求值
    if requested_max and requested_max > 0:
        return min(requested_max, effective_cap)

    return effective_cap


def cap_max_tokens_in_body(
    body: dict[str, Any],
    backend_name: str = "",
    model_id: str = "",
) -> dict[str, Any]:
    """对请求体中的 max_tokens 做封顶处理。

    便捷方法，直接修改 body["max_tokens"] 并返回。

    Args:
        body: 请求体 dict。
        backend_name: 后端名称。
        model_id: 模型标识符。

    Returns:
        修改后的 body (同一对象)。
    """
    current = body.get("max_tokens")
    if not isinstance(current, int) or current <= 0:
        return body

    capped = resolve_max_output_tokens(
        requested_max=current,
        backend_name=backend_name,
        model_id=model_id,
    )

    if capped < current:
        _log.debug(
            "capped max_tokens: %d → %d (backend=%s model=%s)",
            current, capped, backend_name, model_id,
        )
        body["max_tokens"] = capped

    return body
