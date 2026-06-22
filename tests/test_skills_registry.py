"""Tests for skills_registry activation."""

from __future__ import annotations

import json
from pathlib import Path

import skills_registry
import skills_injector


def test_load_registry_skills_from_project_dir():
    root = str(Path(__file__).resolve().parents[1] / "skills")
    skills = skills_registry.load_registry_skills(root)
    ids = {skill["id"] for skill in skills}
    assert "device_drawing" in ids
    assert "honest_uncertainty" in ids
    assert all(skill.get("content") for skill in skills)


def test_select_triggered_skills_by_intent(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "device.md").write_text("device body", encoding="utf-8")
    (skills_dir / "_registry.json").write_text(
        json.dumps(
            {
                "skills": [
                    {
                        "id": "device_drawing",
                        "path": "device.md",
                        "trigger": {"intent": ["device_draw"]},
                        "priority": 10,
                    },
                    {
                        "id": "always_safe",
                        "path": "device.md",
                        "trigger": {"always": True},
                        "priority": 1,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = skills_registry.load_registry_skills(str(skills_dir))
    selected = skills_registry.select_triggered_skills(loaded, intent="device_draw")
    assert [skill["id"] for skill in selected] == ["always_safe", "device_drawing"]


def test_apply_skills_uses_registry_for_weak_backend(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "draw.md").write_text("draw skill body", encoding="utf-8")
    (skills_dir / "_registry.json").write_text(
        json.dumps(
            {
                "skills": [
                    {
                        "id": "device_drawing",
                        "path": "draw.md",
                        "trigger": {"intent": ["device_draw"]},
                        "priority": 10,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    messages = [{"role": "user", "content": "让笔绘机画一只猫"}]
    injected = skills_injector.apply_skills(
        backend="weak-test-backend",
        messages=messages,
        skills_dir=str(skills_dir),
        intent="device_draw",
    )
    assert len(injected) == 2
    assert injected[0]["role"] == "system"
    assert "draw skill body" in injected[0]["content"]
