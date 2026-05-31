"""Static reverse-provider registry.

Reverse providers are intentionally not part of normal routing pools until an
adapter, health probe, auth state, and eval evidence are available.
"""

from __future__ import annotations

from reverse_gateway.models import ReverseProvider


PROVIDERS: dict[str, ReverseProvider] = {
    # M6: duck_web provider deleted — DDG backends removed (not in any routing pool)
    "kimi_web": ReverseProvider(
        name="kimi_web",
        port=4504,
        backends=("kimi", "kimi_thinking", "kimi_search"),
        status="ready_proxy_shell",
        reason="M3: VPS kimi-proxy.service running (Node.js), session deployed.",
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
        status="ready_proxy_shell",
        reason="M4: VPS longcat-web-proxy.service running, cookie_valid=true.",
    ),
    "mimo_web": ReverseProvider(
        name="mimo_web",
        port=4507,
        backends=("mimo_web", "mimo_web_think", "mimo_web_flash", "mimo_web_code", "mimo_web_think_code"),
        status="ready_proxy_shell",
        reason="M5: VPS mimo-proxy.service running, 260 requests/243 success.",
    ),
}


def list_provider_status() -> list[dict[str, object]]:
    return [provider.to_dict() for provider in PROVIDERS.values()]


def provider_status(name: str) -> dict[str, object] | None:
    provider = PROVIDERS.get(name)
    return provider.to_dict() if provider else None
