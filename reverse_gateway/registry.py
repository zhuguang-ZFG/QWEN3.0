"""Static reverse-provider registry.

Reverse providers are intentionally not part of normal routing pools until an
adapter, health probe, auth state, and eval evidence are available.
"""

from __future__ import annotations

from reverse_gateway.models import ReverseProvider


PROVIDERS: dict[str, ReverseProvider] = {
    "duck_web": ReverseProvider(
        name="duck_web",
        port=4500,
        backends=(
            "ddg_gpt4o_mini",
            "ddg_gpt5_mini",
            "ddg_claude_haiku_45",
            "ddg_llama4",
            "ddg_mistral",
            "ddg_tinfoil_gptoss_120b",
        ),
        status="disabled_no_adapter",
        reason="Windows/local proxy source is unavailable.",
    ),
    "kimi_web": ReverseProvider(
        name="kimi_web",
        port=4504,
        backends=("kimi", "kimi_thinking", "kimi_search"),
        status="disabled_no_adapter",
        reason="Auth/quota state requires a VPS adapter and health probe.",
    ),
    "scnet_large": ReverseProvider(
        name="scnet_large",
        port=4505,
        backends=("scnet_large_ds_flash", "scnet_large_ds_pro"),
        status="ready_protocol_adapter",
        reason="M2: VPS sidecar enabled (lima-scnet-reverse.service), protocol + cookies deployed.",
    ),
    "longcat_web": ReverseProvider(
        name="longcat_web",
        port=4506,
        backends=("longcat_web", "longcat_web_think", "longcat_web_research"),
        status="disabled_no_adapter",
        reason="Web proxy source is unavailable.",
    ),
    "mimo_web": ReverseProvider(
        name="mimo_web",
        port=4507,
        backends=("mimo_web", "mimo_web_think", "mimo_web_flash", "mimo_web_code", "mimo_web_think_code"),
        status="disabled_no_adapter",
        reason="Needs a VPS browser/cookie sidecar before routing.",
    ),
}


def list_provider_status() -> list[dict[str, object]]:
    return [provider.to_dict() for provider in PROVIDERS.values()]


def provider_status(name: str) -> dict[str, object] | None:
    provider = PROVIDERS.get(name)
    return provider.to_dict() if provider else None
