"""Test skills/ directory integrity: every .md file must have valid frontmatter."""

import glob
import os

from skills_injector import _parse_frontmatter


_SKILLS_ROOT = os.path.join(os.path.dirname(__file__), "..", "skills")


def _skill_files():
    pattern = os.path.join(_SKILLS_ROOT, "**", "*.md")
    for fpath in glob.glob(pattern, recursive=True):
        yield fpath


def test_all_skill_files_have_frontmatter_id():
    """Every skills/*.md must have frontmatter with at least an id field."""
    missing = []
    for fpath in _skill_files():
        with open(fpath, encoding="utf-8") as f:
            raw = f.read()
        meta, _body = _parse_frontmatter(raw)
        if not meta or "id" not in meta:
            missing.append(os.path.relpath(fpath, _SKILLS_ROOT))
    assert not missing, f"Skills missing frontmatter / id: {missing}"
