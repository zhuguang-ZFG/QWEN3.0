"""Provider kind detection for backend requests.

Maps a LiMa backend name + model ID to the closest OpenCode provider family
string (e.g. "openai", "anthropic", "google", "openai_compatible").

Shared by reasoning_variants and session_options to avoid duplication.
"""

from __future__ import annotations


def detect_provider_kind(backend_name: str, model_id: str) -> str:
    """Map a LiMa backend+model to the closest OpenCode provider family."""
    fn = backend_name.lower()
    mid = model_id.lower() if model_id else ""

    # Premium providers are named directly
    if any(p in fn for p in ("openai",)):
        return "openai"
    if any(p in fn for p in ("anthropic", "claude")):
        return "anthropic"
    if any(p in fn for p in ("google", "gemini", "vertex")):
        return "google"
    if any(p in fn for p in ("groq",)):
        return "groq"
    if any(p in fn for p in ("cerebras",)):
        return "cerebras"
    if any(p in fn for p in ("mistral",)):
        return "mistral"
    if any(p in fn for p in ("xai", "grok")):
        return "xai"
    if any(p in fn for p in ("deepinfra",)):
        return "deepinfra"
    if any(p in fn for p in ("cohere",)):
        return "cohere"
    if any(p in fn for p in ("perplexity",)):
        return "perplexity"
    if any(p in fn for p in ("togetherai", "together")):
        return "togetherai"
    if any(p in fn for p in ("venice",)):
        return "venice"

    # SCNet hosts DeepSeek models
    if "scnet" in fn or "deepseek" in mid or "deepseek" in fn:
        if any(t in mid for t in ("r1", "reasoner", "thinking")):
            return "deepseek_reasoning"
        return "openai_compatible"

    # Kimi family
    if "kimi" in fn or "kimi" in mid or "moonshot" in fn:
        return "kimi"
    if "glm" in mid:
        return "kimi"
    if "qwen" in mid or "qwq" in mid:
        return "qwen"

    if "cf_" in fn:
        return "cloudflare_gateway"
    if "opencode_" in fn:
        return "opencode_zen"
    if "zhipu" in fn:
        return "openai_compatible"

    return "openai_compatible"
