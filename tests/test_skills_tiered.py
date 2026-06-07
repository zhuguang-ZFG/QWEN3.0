"""Tests for L0/L1/L2 tiered skill loading."""
import os
import tempfile

import pytest

from skills_injector import _trim_to_budget, load_skills_from_dir


def test_skill_with_sidecar_abstract(tmp_path):
    """A skill with .abstract sidecar gets abstract field populated."""
    skill_dir = tmp_path / "code"
    skill_dir.mkdir()

    # Main skill file
    (skill_dir / "error_handling.md").write_text(
        "---\nid: error_handling\ncategory: code\n---\n"
        "Full error handling skill content with detailed instructions.",
        encoding="utf-8",
    )
    # L0 abstract sidecar
    (skill_dir / "error_handling.abstract").write_text(
        "Error handling patterns and retry strategies.",
        encoding="utf-8",
    )

    skills = load_skills_from_dir(str(tmp_path))
    assert len(skills) == 1
    assert skills[0]["abstract"] == "Error handling patterns and retry strategies."


def test_skill_without_sidecar_has_empty_abstract(tmp_path):
    """A skill without .abstract sidecar gets empty abstract."""
    skill_dir = tmp_path / "code"
    skill_dir.mkdir()
    (skill_dir / "logging.md").write_text(
        "---\nid: logging\ncategory: code\n---\nLogging best practices.",
        encoding="utf-8",
    )

    skills = load_skills_from_dir(str(tmp_path))
    assert len(skills) == 1
    assert skills[0]["abstract"] == ""


def test_tier_selection_by_budget(tmp_path):
    """When budget is tight, L0 (abstract) is used; otherwise L2 (full)."""
    from skills_injector import select_skill_tier

    skill = {
        "id": "test",
        "abstract": "Short summary",
        "content": "Very long detailed content " * 50,
    }

    # Tight budget -> L0
    tier_text = select_skill_tier(skill, max_tokens=30)
    assert tier_text == "Short summary"

    # Generous budget -> L2 (full content)
    tier_text = select_skill_tier(skill, max_tokens=500)
    assert "Very long detailed content" in tier_text


def test_tier_falls_back_to_content_when_no_abstract():
    """If abstract is empty, fall back to truncated content even on tight budget."""
    from skills_injector import select_skill_tier

    skill = {"id": "test", "abstract": "", "content": "Some content here"}
    tier_text = select_skill_tier(skill, max_tokens=30)
    assert "Some content" in tier_text
