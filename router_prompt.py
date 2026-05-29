"""Prompt fragment assembly extracted from smart_router (CQ-014 slice 7)."""

from __future__ import annotations

import os

FRAGMENT_DIR = os.path.join(os.path.dirname(__file__), "fragments")


def _load_fragment(name: str) -> str:
    path = os.path.join(FRAGMENT_DIR, f"{name}.md")
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return ""


def assemble_prompt(features=None) -> str:
    """Assemble system prompt from static fragment files."""
    if features is None:
        features = {"identity", "capabilities", "constraints", "safety"}
    parts = []
    for name in ["identity", "capabilities", "constraints", "safety"]:
        if name in features:
            chunk = _load_fragment(name)
            if chunk:
                parts.append(chunk)
    return "\n\n".join(parts) if parts else ""


SYS = assemble_prompt()
