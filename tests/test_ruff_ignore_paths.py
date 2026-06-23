"""Regression tests for ruff.toml exclude list (P3-20)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def ruff_excludes():
    text = (ROOT / "ruff.toml").read_text(encoding="utf-8")
    excludes: list[str] = []
    in_exclude = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("exclude"):
            in_exclude = True
            continue
        if not in_exclude:
            continue
        if line.startswith("]"):
            break
        value = line.rstrip(",")
        if value.startswith('"') and value.endswith('"'):
            excludes.append(value[1:-1])
    return excludes


def test_ruff_excludes_local_runtime_dirs(ruff_excludes):
    """.venv310, .test-tmp, .pnpm-store must be excluded to avoid scanning huge local dirs."""
    for name in (".venv310", ".test-tmp", ".pnpm-store"):
        assert name in ruff_excludes, f"{name} missing from ruff.toml exclude"


def test_ruff_excludes_are_real_directories():
    """All anchored exclude entries correspond to directories that exist locally."""
    excludes = {".venv310", ".test-tmp", ".pnpm-store", ".agent", ".codex", ".continue", ".roo", ".trae"}
    for name in excludes:
        path = ROOT / name
        if path.exists():
            assert path.is_dir(), f"{name} exists but is not a directory"
