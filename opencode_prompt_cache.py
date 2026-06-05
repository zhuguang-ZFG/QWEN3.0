"""opencode_prompt_cache.py — Prompt caching 标记注入。

复刻 OpenCode transform.ts applyCaching() (L321-370)。
对 Anthropic / OpenRouter / Bedrock / OpenAI Compatible / Copilot / Alibaba
的消息自动注入缓存控制标记，减少重复请求延迟和成本。

核心功能:
  1. apply_prompt_caching() — 对消息列表注入缓存标记
  2. should_apply_caching() — 判断后端是否需要缓存注入

缓存策略:
  - system 消息前 2 条 + 非 system 消息最后 2 条注入缓存标记
  - 不同后端使用不同的缓存控制字段名
"""

from __future__ import annotations

import logging
from typing import Any

from provider_kind import detect_provider_kind

_log = logging.getLogger(__name__)

# ── Provider-specific cache control options (transform.ts:326-343) ──────────

_PROVIDER_CACHE_OPTIONS: dict[str, dict[str, Any]] = {
    "anthropic": {
        "anthropic": {"cacheControl": {"type": "ephemeral"}},
    },
    "openrouter": {
        "openrouter": {"cacheControl": {"type": "ephemeral"}},
    },
    "bedrock": {
        "bedrock": {"cachePoint": {"type": "default"}},
    },
    "openai_compatible": {
        "openaiCompatible": {"cache_control": {"type": "ephemeral"}},
    },
    "github_copilot": {
        "copilot": {"copilot_cache_control": {"type": "ephemeral"}},
    },
    "alibaba": {
        "alibaba": {"cacheControl": {"type": "ephemeral"}},
    },
}

# Providers that should receive caching headers
_CACHING_PROVIDERS = frozenset({
    "anthropic", "openrouter", "bedrock", "openai_compatible",
    "github_copilot", "alibaba",
})


def should_apply_caching(
    backend_name: str,
    model_id: str,
    provider_kind: str = "",
) -> bool:
    """Check if the backend should receive prompt caching headers.

    Ported from transform.ts:413-425 caching eligibility check.
    """
    pk = provider_kind or detect_provider_kind(backend_name, model_id)
    mid = model_id.lower()

    # Anthropic-family: includes direct Anthropic, Google-Vertex-Anthropic,
    # and any model with "claude" or "anthropic" in the ID
    if pk == "anthropic":
        return True
    if any(t in mid for t in ("anthropic", "claude")):
        return True
    # Alibaba (DashScope)
    if pk == "alibaba" or "alibaba" in backend_name.lower():
        return True
    # Other known caching providers
    if pk in _CACHING_PROVIDERS:
        return True
    # AI Gateway — skip (it uses gateway-level caching)
    if pk == "ai_gateway":
        return False

    return False


def apply_prompt_caching(
    messages: list[dict],
    backend_name: str,
    model_id: str,
    provider_kind: str = "",
) -> list[dict]:
    """Inject prompt caching markers into messages.

    Ported from transform.ts applyCaching() (L321-370).
    Selects system messages (first 2) and non-system messages (last 2),
    then injects provider-specific cache control options.

    Args:
        messages: Message list (will not be mutated; returns new list).
        backend_name: Backend identifier.
        model_id: Model identifier.
        provider_kind: Optional pre-computed provider kind.

    Returns:
        New message list with caching markers injected.
    """
    pk = provider_kind or detect_provider_kind(backend_name, model_id)

    if not should_apply_caching(backend_name, model_id, pk):
        return messages

    cache_opts = _PROVIDER_CACHE_OPTIONS.get(pk)
    if not cache_opts:
        return messages

    # Select target messages: first 2 system + last 2 non-system
    system_indices = [i for i, m in enumerate(messages) if m.get("role") == "system"]
    non_system_indices = [i for i, m in enumerate(messages) if m.get("role") != "system"]

    target_indices: set[int] = set()
    for idx in system_indices[:2]:
        target_indices.add(idx)
    for idx in non_system_indices[-2:]:
        target_indices.add(idx)

    if not target_indices:
        return messages

    result = list(messages)
    for i in target_indices:
        msg = result[i]
        content = msg.get("content", "")

        # For array content, inject on the last content part
        if isinstance(content, list) and content:
            last_part = content[-1]
            if isinstance(last_part, dict) and last_part.get("type") not in (
                "tool-approval-request", "tool-approval-response",
            ):
                existing_opts = last_part.get("providerOptions") or {}
                merged = _deep_merge(existing_opts, cache_opts)
                new_part = {**last_part, "providerOptions": merged}
                new_content = list(content)
                new_content[-1] = new_part
                result[i] = {**msg, "content": new_content}
                continue

        # For string content or empty array, inject at message-level providerOptions
        existing_opts = msg.get("providerOptions") or {}
        merged = _deep_merge(existing_opts, cache_opts)
        result[i] = {**msg, "providerOptions": merged}

    _log.debug(
        "Applied prompt caching to %d/%d messages (provider=%s)",
        len(target_indices), len(messages), pk,
    )
    return result


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dicts, override wins on conflict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
