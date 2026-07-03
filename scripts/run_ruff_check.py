#!/usr/bin/env python3
"""Run ``ruff check`` then ``ruff format --check`` against tracked or provided Python files.

The format check is bundled here so local pre-commit catches the same style
drift that CI's ``ruff format --check`` step would (lesson learned O-3:
``ruff check`` was clean locally but ``ruff format --check`` failed in CI on
slice spacing, blocking the build and forcing a follow-up fix commit).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

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
    """Run ``ruff check`` then ``ruff format --check`` against ``paths``.

    Both must pass — the format check catches style drift (slice spacing,
    Optional[X] vs X|None, EOL newline) that ``ruff check`` cannot, and which
    would otherwise only surface in CI's separate ``ruff format --check`` step
    (lesson learned O-3 batch 2026-07-03: locally ``ruff check`` was clean but
    ``ruff format --check`` failed on slice spacing, blocking CI).
    Aggregates stdout/stderr; returns the first non-zero returncode (or 0).
    """
    if not paths:
        return subprocess.CompletedProcess(["ruff", "check"], 0, "no tracked Python files\n", "")
    # Use an argument file to avoid Windows command-line length limits.
    argfile = root / ".ruff-check-paths"
    argfile.write_text("\n".join(paths), encoding="utf-8")
    try:
        check_result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--force-exclude", f"@{argfile}"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        format_result = subprocess.run(
            [sys.executable, "-m", "ruff", "format", "--check", f"@{argfile}"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    finally:
        argfile.unlink(missing_ok=True)
    rc = check_result.returncode or format_result.returncode
    combined_out = check_result.stdout + format_result.stdout
    combined_err = check_result.stderr + format_result.stderr
    return subprocess.CompletedProcess(["ruff", "check+format"], rc, combined_out, combined_err)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Python files to check; defaults to all tracked Python files",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        paths = args.paths if args.paths else tracked_python_files()
        result = run_ruff(paths)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
