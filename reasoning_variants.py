"""Reasoning/thinking variant computation for backend models.

Ported from OpenCode's `packages/opencode/src/provider/transform.ts:614-1025`.
For a given backend+model, returns the available reasoning_effort / thinking
tiers AND how to translate an effort level into provider-specific request
body parameters.
"""

from __future__ import annotations

import re

from provider_kind import detect_provider_kind

WIDELY_SUPPORTED_EFFORTS = ["low", "medium", "high"]
OPENAI_EFFORTS = ["none", "minimal", "low", "medium", "high", "xhigh"]
OPENAI_GPT5_1_EFFORTS = ["none", "low", "medium", "high"]
OPENAI_GPT5_2_PLUS_EFFORTS = ["none", "low", "medium", "high", "xhigh"]
OPENAI_GPT5_PRO_EFFORTS = ["high"]
OPENAI_GPT5_PRO_2_PLUS_EFFORTS = ["medium", "high", "xhigh"]
OPENAI_GPT5_CHAT_EFFORTS = ["medium"]
OPENAI_GPT5_CODEX_XHIGH_EFFORTS = ["low", "medium", "high", "xhigh"]
OPENAI_GPT5_CODEX_3_PLUS_EFFORTS = ["none", "low", "medium", "high", "xhigh"]

GPT5_FAMILY_RE = re.compile(r"(?:^|/)gpt-5(?:[.-]|$)")
GPT5_VERSION_RE = re.compile(r"(?:^|/)gpt-5[.-](\d+)(?:[.-]|$)")
GPT5_PRO_RE = re.compile(r"(?:^|/)gpt-5[.-]?pro(?:[.-]|$)")
GPT5_VERSIONED_PRO_RE = re.compile(r"(?:^|/)gpt-5[.-]\d+[.-]pro(?:[.-]|$)")


def _gpt5_version(api_id: str) -> int | None:
    m = GPT5_VERSION_RE.search(api_id)
    return int(m.group(1)) if m else None


def _versioned_gpt5_efforts(api_id: str):
    if GPT5_VERSIONED_PRO_RE.search(api_id):
        return OPENAI_GPT5_PRO_2_PLUS_EFFORTS
    v = _gpt5_version(api_id)
    if v is None:
        return None
    if v == 1:
        return OPENAI_GPT5_1_EFFORTS
    return OPENAI_GPT5_2_PLUS_EFFORTS


def _gpt5_codex_efforts(api_id: str):
    if not GPT5_FAMILY_RE.search(api_id) or "codex" not in api_id:
        return None
    v = _gpt5_version(api_id)
    if v is not None and v >= 3:
        return OPENAI_GPT5_CODEX_3_PLUS_EFFORTS
    if "codex-max" in api_id or (v is not None and v >= 2):
        return OPENAI_GPT5_CODEX_XHIGH_EFFORTS
    return WIDELY_SUPPORTED_EFFORTS


def _gpt5_chat_efforts(api_id: str):
    if not GPT5_FAMILY_RE.search(api_id) or "-chat" not in api_id:
        return None
    return [] if _gpt5_version(api_id) is None else OPENAI_GPT5_CHAT_EFFORTS


def openai_reasoning_efforts(api_id: str, release_date: str = "") -> list[str]:
    """Compute the reasoning_effort tiers supported by a GPT/OpenAI model."""
    aid = api_id.lower()
    if "deep-research" in aid:
        return ["medium"]
    chat = _gpt5_chat_efforts(aid)
    if chat is not None:
        return chat
    if GPT5_PRO_RE.search(aid):
        return OPENAI_GPT5_PRO_EFFORTS
    codex = _gpt5_codex_efforts(aid)
    if codex is not None:
        return codex
    versioned = _versioned_gpt5_efforts(aid)
    if versioned is not None:
        return versioned
    efforts = list(WIDELY_SUPPORTED_EFFORTS)
    if GPT5_FAMILY_RE.search(aid):
        efforts.insert(0, "minimal")
    if release_date >= "2025-11-13":
        efforts.insert(0, "none")
    if release_date >= "2025-12-04":
        efforts.append("xhigh")
    return efforts


def openai_compatible_efforts(api_id: str) -> list[str]:
    aid = api_id.lower()
    chat = _gpt5_chat_efforts(aid)
    if chat is not None:
        return chat
    if GPT5_PRO_RE.search(aid):
        return OPENAI_GPT5_PRO_EFFORTS
    codex = _gpt5_codex_efforts(aid)
    if codex is not None:
        return codex
    versioned = _versioned_gpt5_efforts(aid)
    if versioned is not None:
        return versioned
    return list(OPENAI_EFFORTS)


def _anthropic_opus_47_or_later(api_id: str) -> bool:
    m = re.search(
        r"opus-(\d+)[.-](\d+)(?:[.@-]|$)|claude-(\d+)[.-](\d+)-opus(?:[.@-]|$)",
        api_id,
        re.IGNORECASE,
    )
    if not m:
        return False
    major = int(m.group(1) or m.group(3))
    minor = int(m.group(2) or m.group(4))
    return major > 4 or (major == 4 and minor >= 7)


def _anthropic_adaptive_efforts(api_id: str) -> list[str] | None:
    if _anthropic_opus_47_or_later(api_id):
        return ["low", "medium", "high", "xhigh", "max"]
    _46_ids = ["opus-4-6", "opus-4.6", "4-6-opus", "4.6-opus", "sonnet-4-6", "sonnet-4.6", "4-6-sonnet", "4.6-sonnet"]
    if any(v in api_id for v in _46_ids):
        return ["low", "medium", "high", "max"]
    return None


def _google_thinking_level_efforts(api_id: str) -> list[str]:
    aid = api_id.lower()
    if "gemini-3" not in aid:
        return ["low", "high"]
    if "flash-image" in aid:
        return ["minimal", "high"]
    if "pro-image" in aid:
        return ["high"]
    if "flash" in aid:
        return ["minimal", "low", "medium", "high"]
    return ["low", "medium", "high"]


_MISTRAL_REASONING_IDS = [
    "mistral-small-2603", "mistral-small-latest",
    "mistral-medium-3.5", "mistral-medium-2604",
]


def compute_variants(
    backend_name: str,
    model_id: str,
    provider_kind: str = "",
    reasoning_capable: bool = True,
    release_date: str = "",
) -> dict[str, dict[str, object]]:
    """Return the reasoning/thinking variants for a backend+model.

    Returns a dict mapping effort tier name to provider-specific body params.
    An empty dict means reasoning is not supported for this backend.
    """
    if not reasoning_capable:
        return {}

    pk = provider_kind or detect_provider_kind(backend_name, model_id)
    mid = model_id.lower()

    # Models that always return {} — reasoning is provider-handled or unsupported
    if any(t in mid for t in ("deepseek-chat", "deepseek-reasoner", "deepseek-r1",
                                "deepseek-v3", "minimax", "glm", "kimi", "k2p",
                                "qwen", "big-pickle")):
        return {}

    if "grok" in mid and "grok-3-mini" in mid:
        return {"low": {"reasoningEffort": "low"}, "high": {"reasoningEffort": "high"}}
    if "grok" in mid:
        return {}

    match pk:
        case "openrouter":
            if not any(t in mid for t in ("gpt", "gemini-3", "claude")):
                return {}
            efforts = openai_compatible_efforts(model_id) if "gpt" in mid else OPENAI_EFFORTS
            return {e: {"reasoning": {"effort": e}} for e in efforts}

        case "cloudflare_gateway":
            if "openai/" in mid or any(mid.startswith(p) for p in ("gpt-", "o1", "o3")):
                efforts = openai_reasoning_efforts(mid, release_date)
                return {e: {"reasoningEffort": e} for e in efforts}
            return {e: {"reasoningEffort": e} for e in WIDELY_SUPPORTED_EFFORTS}

        case "anthropic":
            adaptive = _anthropic_adaptive_efforts(mid)
            if adaptive:
                result = {}
                for effort in adaptive:
                    opts: dict[str, object] = {
                        "thinking": {"type": "adaptive"},
                        "effort": effort,
                    }
                    if isinstance(opts["thinking"], dict) and _anthropic_opus_47_or_later(mid):
                        opts["thinking"]["display"] = "summarized"  # type: ignore[index]
                    result[effort] = opts
                return result
            if any(v in mid for v in ("opus-4-5", "opus-4.5")):
                return {e: {"effort": e} for e in WIDELY_SUPPORTED_EFFORTS}
            return {
                "high": {"thinking": {"type": "enabled", "budgetTokens": 16000}},
                "max": {"thinking": {"type": "enabled", "budgetTokens": 31999}},
            }

        case "google":
            if "2.5" in mid:
                budget_max = 32768 if "pro" in mid and "flash" not in mid else 24576
                return {
                    "high": {"thinkingConfig": {"includeThoughts": True, "thinkingBudget": 16000}},
                    "max": {"thinkingConfig": {"includeThoughts": True, "thinkingBudget": budget_max}},
                }
            return {
                e: {"thinkingConfig": {"includeThoughts": True, "thinkingLevel": e}}
                for e in _google_thinking_level_efforts(mid)
            }

        case "groq" | "cerebras" | "togetherai" | "xai" | "deepinfra" | "venice" | "openai_compatible":
            efforts = list(WIDELY_SUPPORTED_EFFORTS)
            if "deepseek-v4" in mid:
                efforts.append("max")
            return {e: {"reasoningEffort": e} for e in efforts}

        case "openai":
            efforts = openai_reasoning_efforts(model_id, release_date)
            return {e: {"reasoningEffort": e, "reasoningSummary": "auto",
                         "include": ["reasoning.encrypted_content"]} for e in efforts}

        case "azure":
            if model_id.lower() == "o1-mini":
                return {}
            efforts = openai_reasoning_efforts(model_id, release_date)
            return {e: {"reasoningEffort": e, "reasoningSummary": "auto",
                         "include": ["reasoning.encrypted_content"]} for e in efforts}

        case "github_copilot":
            if "gemini" in mid:
                return {}
            if "claude" in mid:
                return {e: {"reasoningEffort": e} for e in WIDELY_SUPPORTED_EFFORTS}
            if any(v in mid for v in ("5.1-codex-max", "5.2", "5.3")):
                efforts = list(WIDELY_SUPPORTED_EFFORTS) + ["xhigh"]
            else:
                efforts = list(WIDELY_SUPPORTED_EFFORTS)
                if "gpt-5" in mid and release_date >= "2025-12-04":
                    efforts.append("xhigh")
            return {e: {"reasoningEffort": e, "reasoningSummary": "auto",
                         "include": ["reasoning.encrypted_content"]} for e in efforts}

        case "bedrock":
            # Bedrock uses reasoningConfig (not thinking) — transform.ts:855-900
            adaptive = _anthropic_adaptive_efforts(mid)
            if adaptive:
                is_opus47 = _anthropic_opus_47_or_later(mid)
                result = {}
                for effort in adaptive:
                    rc: dict[str, object] = {
                        "type": "adaptive",
                        "maxReasoningEffort": effort,
                    }
                    if is_opus47:
                        rc["display"] = "summarized"
                    result[effort] = {"reasoningConfig": rc}
                return result

            # Anthropic models on Bedrock: budgetTokens
            if "anthropic" in mid or "claude" in mid:
                return {
                    "high": {"reasoningConfig": {"type": "enabled", "budgetTokens": 16000}},
                    "max": {"reasoningConfig": {"type": "enabled", "budgetTokens": 31999}},
                }

            # Nova / other models: maxReasoningEffort
            return {
                e: {"reasoningConfig": {"type": "enabled", "maxReasoningEffort": e}}
                for e in WIDELY_SUPPORTED_EFFORTS
            }

        case "mistral":
            if not any(v in mid for v in _MISTRAL_REASONING_IDS):
                return {}
            return {"high": {"reasoningEffort": "high"}}

        case _:
            return {}


def apply_variant(
    backend_name: str,
    model_id: str,
    effort: str,
    provider_kind: str = "",
    reasoning_capable: bool = True,
) -> dict[str, object]:
    """Translate a reasoning_effort value into backend-specific body params.

    Returns the provider-specific options dict to merge into the request body,
    or an empty dict if the effort level is not supported.
    """
    variants = compute_variants(backend_name, model_id, provider_kind, reasoning_capable)
    if not variants or effort not in variants:
        return {}
    return dict(variants[effort])


def list_efforts(
    backend_name: str,
    model_id: str,
    provider_kind: str = "",
    reasoning_capable: bool = True,
) -> list[str]:
    """Return the list of supported reasoning_effort tiers for a backend."""
    return list(compute_variants(backend_name, model_id, provider_kind, reasoning_capable).keys())
