"""Skill injection helpers for routing_engine."""

from __future__ import annotations

import logging

import skills_injector as skills_mod

_log = logging.getLogger(__name__)


def inject_skills(
    messages: list[dict],
    *,
    backend: str = "",
    ide_source: str = "",
    system_prompt: str = "",
) -> list[dict]:
    """Inject backend-aware skills for IDE and coding requests."""
    return skills_mod.apply_skills(
        backend=backend,
        messages=messages,
        system_prompt=system_prompt,
        ide_source=ide_source,
    )


def apply_backend_aware_skills(
    messages: list[dict],
    backend: str,
    *,
    ide_source: str = "",
    system_prompt: str = "",
) -> list[dict]:
    """Re-inject skills with the actual backend known.

    When the early injection used backend="" (unknown), all skills may have been
    injected in weak-model mode.  This second pass uses the real backend so that
    strong models get directory mode (skill names only) and weak models get the
    provider-specific reasoning hints from opencode_reasoning_bridge.
    """
    if not backend:
        return messages
    try:
        return skills_mod.apply_skills(
            backend=backend,
            messages=messages,
            system_prompt=system_prompt,
            ide_source=ide_source,
        )
    except Exception as exc:
        _log.debug("backend_aware_skills injection failed: %s", exc)
        return messages


def get_injected_ids(original: list[dict], modified: list[dict]) -> list[str]:
    """Extract injected skill IDs from the additional system prompt."""
    if len(modified) <= len(original):
        return []
    for msg in modified:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if "Available skills:" in content:
                names = content.replace("Available skills:", "").strip()
                return ["dir:" + name.strip() for name in names.split(",") if name.strip()]
    extra = len(modified) - len(original)
    return [f"injected_{extra}_skills"] if extra > 0 else []
