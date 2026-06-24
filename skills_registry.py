"""Registry-based skill activation for scenario/intent triggers."""

from __future__ import annotations

import json
import os
from typing import Any


def _read_skill_body(fpath: str) -> str:
    with open(fpath, encoding="utf-8") as handle:
        raw = handle.read()
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            return raw[end + 4 :].strip()
    return raw.strip()


def load_registry_skills(skills_dir: str) -> list[dict[str, Any]]:
    """Load skills declared in skills/_registry.json.

    Coding skills are filtered out because the coding capability was retired in v3.0.
    """
    registry_path = os.path.join(skills_dir, "_registry.json")
    if not os.path.isfile(registry_path):
        return []

    with open(registry_path, encoding="utf-8") as handle:
        data = json.load(handle)

    skills: list[dict[str, Any]] = []
    for entry in data.get("skills", []):
        if not isinstance(entry, dict):
            continue
        rel_path = entry.get("path")
        skill_id = entry.get("id")
        if not isinstance(rel_path, str) or not isinstance(skill_id, str):
            continue
        if entry.get("category") == "code":
            continue
        fpath = os.path.join(skills_dir, rel_path)
        if not os.path.isfile(fpath):
            continue
        skills.append(
            {
                "id": skill_id,
                "category": entry.get("category", "general"),
                "content": _read_skill_body(fpath),
                "detect_keywords": entry.get("detect_keywords", []),
                "always_apply": bool(entry.get("always_apply")),
                "priority": int(entry.get("priority", 5)),
                "trigger": entry.get("trigger", {}),
            }
        )
    return skills


def select_triggered_skills(
    registry_skills: list[dict[str, Any]],
    *,
    intent: str = "",
    route_role: str = "",
    scenario: str = "",
) -> list[dict[str, Any]]:
    """Pick registry skills whose trigger matches the current request context.

    Coding skills are ignored because the coding capability was retired in v3.0.
    """
    selected: dict[str, dict[str, Any]] = {}
    for skill in registry_skills:
        if skill.get("category") == "code":
            continue
        trigger = skill.get("trigger") or {}
        matched = bool(trigger.get("always")) or skill.get("always_apply")
        if not matched and intent and intent in trigger.get("intent", []):
            matched = True
        if not matched and route_role and route_role in trigger.get("route_role", []):
            matched = True
        if not matched and scenario and scenario in trigger.get("scenario", []):
            matched = True
        if matched:
            selected[skill["id"]] = skill

    ordered = sorted(selected.values(), key=lambda item: item.get("priority", 5))
    return ordered
