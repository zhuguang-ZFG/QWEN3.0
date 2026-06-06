"""OpenCode prompt injection helpers for routing_engine coding path."""

from __future__ import annotations

import logging
from typing import Callable


def inject_coding_opencode_prompts(
    messages: list[dict],
    *,
    system_prompt: str,
    tools: list[dict] | None,
    headers: dict,
    needs_tools: bool,
    ide_source: str,
    health_map_getter: Callable[[], dict],
    selector: Callable[..., list[str]],
) -> list[dict]:
    try:
        from opencode_tool_aware import inject_opencode_prompt

        messages = inject_opencode_prompt(
            messages,
            backend="",
            system_prompt=system_prompt,
            tools=tools,
            headers=headers,
        )
    except (ImportError, Exception) as exc:
        logging.debug("routing_engine: opencode_tool_aware failed: %s", exc)

    try:
        estimated_backend = _estimate_backend(
            needs_tools=needs_tools,
            ide_source=ide_source,
            health_map_getter=health_map_getter,
            selector=selector,
        )
        if estimated_backend:
            messages = _inject_reasoning_bridge(messages, estimated_backend)
            messages = _inject_sequential_tool_hint(messages, estimated_backend, tools)
    except (ImportError, Exception) as exc:
        logging.debug("routing_engine: reasoning_bridge failed: %s", exc)

    return messages


def _estimate_backend(
    *,
    needs_tools: bool,
    ide_source: str,
    health_map_getter: Callable[[], dict],
    selector: Callable[..., list[str]],
) -> str:
    try:
        candidates = selector(
            "ide",
            health_map_getter(),
            scenario="coding",
            needs_tools=needs_tools,
            ide_source=ide_source,
        )
        return candidates[0] if candidates else ""
    except Exception:
        return ""


def _inject_reasoning_bridge(messages: list[dict], backend: str) -> list[dict]:
    from opencode_reasoning_bridge import inject_thinking_reminder, select_provider_system_prompt

    messages = inject_thinking_reminder(messages, backend)
    provider_hint = select_provider_system_prompt(backend)
    if not provider_hint:
        return messages
    system_index = next((i for i, msg in enumerate(messages) if msg.get("role") == "system"), -1)
    if system_index >= 0:
        old_content = messages[system_index].get("content", "")
        if isinstance(old_content, str):
            messages[system_index] = {
                **messages[system_index],
                "content": old_content.rstrip() + "\n" + provider_hint,
            }
    return messages


def _inject_sequential_tool_hint(messages: list[dict], backend: str, tools: list[dict] | None) -> list[dict]:
    try:
        from opencode_tool_splitter import build_sequential_tool_prompt, should_inject_sequential_hint

        if not should_inject_sequential_hint(backend):
            return messages
        sequential_hint = build_sequential_tool_prompt(tools)
        if not sequential_hint:
            return messages
        system_index = next((i for i, msg in enumerate(messages) if msg.get("role") == "system"), -1)
        if system_index >= 0:
            old_content = messages[system_index].get("content", "")
            if isinstance(old_content, str):
                messages[system_index] = {
                    **messages[system_index],
                    "content": old_content.rstrip() + "\n" + sequential_hint,
                }
        else:
            messages.insert(0, {"role": "system", "content": sequential_hint})
    except (ImportError, Exception) as exc:
        logging.debug("routing_engine: tool_splitter hint failed: %s", exc)
    return messages
