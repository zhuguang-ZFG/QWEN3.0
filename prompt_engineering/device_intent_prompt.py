"""Merge device-intent prompt layers into chat system prompts."""

from __future__ import annotations

from prompt_engineering.layers import compose_system_prompt
from routing_intent import analyze_intent, intent_to_prompt_scenario


def merge_device_intent_system_prompt(
    query: str,
    system_prompt: str,
    *,
    ide_source: str = "",
) -> str:
    """When query matches a device intent, compose device scenario layers on top of existing prompt."""
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return system_prompt

    intent = str(
        analyze_intent(
            cleaned_query,
            system_prompt=system_prompt or "",
            ide=ide_source or "unknown",
        ).get("intent", "chat")
    )
    scenario = intent_to_prompt_scenario(intent)
    if not scenario:
        return system_prompt

    ide = ide_source if ide_source and ide_source not in ("unknown", "未知") else ""
    return compose_system_prompt(
        ide=ide,
        scenario=scenario,
        code_context=system_prompt if system_prompt else "",
    )
