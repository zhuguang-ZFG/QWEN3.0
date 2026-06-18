"""Backend cost classification for budget manager."""

from __future__ import annotations

# free = never block or count against quota
# limited = counted, warn_at 80%, block at 100%
# paid = never block (pay-as-you-go), just track
COST_CLASS: dict[str, str] = {}

# Local / free-tier backends
_LOCAL_BACKENDS = {
    "local_coder14b",
    "local_reasoning",
    "local_general",
    "local_fast",
    "local_chat",
    "local_qwen3",
    "local_phi4",
    "local_mistral",
    "deepseek_free",
}
_FREE_BACKENDS = {
    "chat_ubi",
    "llm7",
    "pollinations",
    "pollinations_openai",
    "pollinations_openai_large",
    "pollinations_deepseek",
    "pollinations_qwen_coder",
    "scnet_qwen30b",
    "scnet_qwen235b",
    "scnet_ds_flash",
    "scnet_ds_pro",
    "scnet_minimax",
    "ovh_llama70b",
    "ovh_deepseek",
    "cfai_llama70b",
    "cfai_llama4",
    "cfai_qwen_coder",
    "cfai_deepseek_r1",
    "cfai_mistral",
    "tele_reason",
    "tele_standard",
    "tele_apps",
    "assist_brainstorm",
    "vision_joycaption",
    "stock_gpt4o_mini",
    "stock_gemini_flash",
    "stock_deepseek",
    "stock_llama4",
    "stock_kimi_k2",
    "stock_glm46",
    "stock_qwen3_coder",
    "stock_news",
    "stock_mistral",
    "oldllm_gpt54",
    "oldllm_gpt53",
    "oldllm_gpt52",
    "oldllm_gpt51",
    "oldllm_gpt5",
    "oldllm_gpt5_mini",
    "oldllm_gpt41",
    "oldllm_gpt41_mini",
    "oldllm_gpt41_nano",
    "oldllm_gpt4",
    "oldllm_o1",
    "oldllm_o4_mini",
}


def _build_cost_class() -> None:
    for b in _LOCAL_BACKENDS:
        COST_CLASS[b] = "free"
    for b in _FREE_BACKENDS:
        COST_CLASS.setdefault(b, "free")


_build_cost_class()


def get_cost_class(backend: str) -> str:
    """free | limited | paid. Unknown backends default to 'limited' (conservative)."""
    return COST_CLASS.get(backend, "limited")


def should_track_cost(backend: str) -> bool:
    """Free/local backends never block on cost. Limited backends do."""
    return get_cost_class(backend) != "free"
