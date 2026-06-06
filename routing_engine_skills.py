"""Skill injection helpers for routing_engine."""

from __future__ import annotations

import skills_injector as skills_mod


def inject_skills(messages: list[dict], *, backend: str = "", ide_source: str = "", system_prompt: str = "") -> list[dict]:
    """Inject backend-aware skills for IDE and coding requests."""
    return skills_mod.apply_skills(
        backend=backend,
        messages=messages,
        system_prompt=system_prompt,
        ide_source=ide_source,
    )


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
