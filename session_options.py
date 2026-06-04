"""Session-level options injection for backend requests.

Ported from OpenCode's `packages/opencode/src/provider/transform.ts:1027-1168`.
Computes per-provider request body options (store/enable_thinking/toolStreaming/
usage/include/promptCacheKey etc.) that must be injected to match OpenCode's
expected behavior.
"""

from __future__ import annotations

from provider_kind import detect_provider_kind


def resolve_session_options(
    backend_name: str,
    model_id: str,
    provider_kind: str = "",
    session_id: str = "",
    reasoning_capable: bool = False,
) -> dict[str, object]:
    """Return provider-specific options to merge into the request body."""
    result: dict[str, object] = {}
    pk = provider_kind or detect_provider_kind(backend_name, model_id)
    mid = model_id.lower()

    # toolStreaming=false for Anthropic (non-Claude) and Vertex-Anthropic
    # When using Anthropic SDK for non-Claude models, tool streaming is broken
    if pk == "anthropic" and "claude" not in mid:
        result["toolStreaming"] = False

    # store=false for OpenAI/Copilot — enables stateless multi-turn reasoning
    if pk in ("openai", "azure", "github_copilot", "opencode_zen"):
        result["store"] = False

    if pk == "azure":
        if session_id:
            result["promptCacheKey"] = session_id

    # OpenRouter / LLMGateway: always include usage
    if pk == "openrouter":
        result["usage"] = {"include": True}
        if "gemini-3" in mid:
            result["reasoning"] = {"effort": "high"}

    # enable_thinking for specific models on opencode zen / baseten
    if pk == "opencode_zen" and any(t in mid for t in ("kimi-k2-thinking", "glm-4.6")):
        result["chat_template_args"] = {"enable_thinking": True}

    # ZhipuAI: thinking enabled with clear_thinking=false
    if "zhipu" in backend_name.lower() and pk == "openai_compatible":
        result["thinking"] = {"type": "enabled", "clear_thinking": False}

    # OpenAI provider: set promptCacheKey with session ID
    if pk == "openai" and session_id:
        result["promptCacheKey"] = session_id

    # Google: enable thinking for reasoning models
    if pk == "google" and reasoning_capable:
        tc: dict[str, object] = {"includeThoughts": True}
        if "gemini-3" in mid:
            tc["thinkingLevel"] = "high"
        result["thinkingConfig"] = tc

    # Kimi via Anthropic SDK: enable thinking
    if pk == "anthropic" and any(t in mid for t in ("k2p", "kimi-k2.", "kimi-k2p")):
        result["thinking"] = {"type": "enabled", "budgetTokens": 16000}

    # DashScope / alibaba-cn: enable_thinking for reasoning models
    if "alibaba" in backend_name.lower() and reasoning_capable and "kimi-k2-thinking" not in mid:
        result["enable_thinking"] = True

    # GPT-5 family: default reasoning_effort=medium, textVerbosity=low
    if "gpt-5" in mid and "gpt-5-chat" not in mid and "gpt-5-pro" not in mid:
        result["reasoningEffort"] = "medium"
        result["reasoningSummary"] = "auto"
        if pk == "openai":
            result["include"] = ["reasoning.encrypted_content"]

    if "gpt-5." in mid and "codex" not in mid and "-chat" not in mid and pk != "azure":
        result["textVerbosity"] = "low"

    # opencode zen provider: promptCache + include encrypted reasoning for GPT-5
    if pk == "opencode_zen" and "gpt-5" in mid:
        if session_id:
            result["promptCacheKey"] = session_id
        result["include"] = ["reasoning.encrypted_content"]
        result["reasoningSummary"] = "auto"

    # Venice: promptCacheKey
    if pk == "venice" and session_id:
        result["promptCacheKey"] = session_id

    # OpenRouter: prompt cache key
    if pk == "openrouter" and session_id:
        result["prompt_cache_key"] = session_id

    # AI Gateway: auto caching
    if pk == "ai_gateway":
        result["gateway"] = {"caching": "auto"}

    return result

