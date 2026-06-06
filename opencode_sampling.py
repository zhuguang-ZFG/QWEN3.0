"""opencode_sampling.py — 模型级采样参数优化。

复刻 OpenCode transform.ts temperature() / topP() / topK() (L457-492)。
不同模型家族对 temperature / top_p / top_k 有不同最优值，
OpenCode 按模型 ID 模式匹配设置采样参数以提升响应质量。

核心功能:
  1. resolve_temperature() — 按模型 ID 返回最优 temperature
  2. resolve_top_p() — 按模型 ID 返回最优 top_p
  3. resolve_top_k() — 按模型 ID 返回最优 top_k
  4. resolve_sampling_params() — 综合入口，返回非 None 的采样参数 dict
"""

from __future__ import annotations

# ── temperature (transform.ts:457-473) ───────────────────────────────────────

def resolve_temperature(model_id: str) -> float | None:
    """Return the optimal temperature for a model, or None to use backend default.

    Ported from transform.ts temperature() (L457-473).
    """
    mid = model_id.lower()

    if "qwen" in mid:
        return 0.55
    if "claude" in mid:
        return None  # Anthropic recommends not setting temperature
    if "gemini" in mid:
        return 1.0
    if "glm-4.6" in mid or "glm-4.7" in mid:
        return 1.0
    if "minimax-m2" in mid:
        return 1.0

    # Kimi K2 variants
    if "kimi-k2" in mid:
        # kimi-k2-thinking, kimi-k2.5, kimi-k2p5, kimi-k2-5
        if any(s in mid for s in ("thinking", "k2.", "k2p", "k2-5")):
            return 1.0
        return 0.6

    return None  # Let backend decide


# ── top_p (transform.ts:475-482) ─────────────────────────────────────────────

def resolve_top_p(model_id: str) -> float | None:
    """Return the optimal top_p for a model, or None to use backend default.

    Ported from transform.ts topP() (L475-482).
    """
    mid = model_id.lower()

    if "qwen" in mid:
        return 1.0
    if any(s in mid for s in ("minimax-m2", "gemini", "kimi-k2.5", "kimi-k2p5", "kimi-k2-5")):
        return 0.95

    return None


# ── top_k (transform.ts:484-492) ─────────────────────────────────────────────

def resolve_top_k(model_id: str) -> int | None:
    """Return the optimal top_k for a model, or None to use backend default.

    Ported from transform.ts topK() (L484-492).
    """
    mid = model_id.lower()

    if "minimax-m2" in mid:
        if any(s in mid for s in ("m2.", "m25", "m21")):
            return 40
        return 20
    if "gemini" in mid:
        return 64

    return None


# ── Combined entry point ─────────────────────────────────────────────────────

def resolve_sampling_params(
    model_id: str,
    backend_name: str = "",
) -> dict[str, float | int]:
    """Resolve all sampling parameters for a model.

    Returns a dict with only non-None values, ready to merge into the request body.
    Keys: temperature, top_p, top_k (OpenAI-compatible naming).

    Args:
        model_id: The model identifier (e.g. "qwen-2.5-coder-32b").
        backend_name: Optional backend name for future extensions.

    Returns:
        Dict like {"temperature": 0.55} or {} if all defaults.
    """
    result: dict[str, float | int] = {}

    temp = resolve_temperature(model_id)
    if temp is not None:
        result["temperature"] = temp

    tp = resolve_top_p(model_id)
    if tp is not None:
        result["top_p"] = tp

    tk = resolve_top_k(model_id)
    if tk is not None:
        result["top_k"] = tk

    return result
