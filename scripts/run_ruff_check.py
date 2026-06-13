#!/usr/bin/env python3
"""Run ruff check against tracked Python files only."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tracked_python_files(root: Path = ROOT) -> list[str]:
    """Return git-tracked Python paths so scratch files do not affect CI gates."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py", "*.pyi"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed: {stderr}")
    root_path = Path(root)
    return [
        path
        for path in result.stdout.decode("utf-8", errors="replace").split("\0")
        if path and path.endswith((".py", ".pyi")) and (root_path / path).exists()
    ]


def run_ruff(paths: list[str], root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    if not paths:
        return subprocess.CompletedProcess(["ruff", "check"], 0, "no tracked Python files\n", "")
    return subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--force-exclude", *paths],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def main() -> int:
    try:
        result = run_ruff(tracked_python_files())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
