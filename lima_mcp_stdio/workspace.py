"""Workspace resolution for global MiMo MCP (any git project)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def resolve_workspace(explicit: str | None = None) -> Path:
    """Pick project root: explicit arg > MIMO_MCP_WORKSPACE > git root > cwd."""
    cwd = Path.cwd().resolve()
    if explicit and explicit.strip():
        candidate = Path(explicit.strip()).expanduser().resolve()
        _require_within_workspace(candidate, cwd)
        return candidate
    env = os.environ.get("MIMO_MCP_WORKSPACE", "").strip()
    if env:
        candidate = Path(env).expanduser().resolve()
        _require_within_workspace(candidate, cwd)
        return candidate
    git_root = _git_root(cwd)
    return git_root or cwd


def _require_within_workspace(path: Path, anchor: Path) -> None:
    """Reject paths that escape the current working tree (path traversal guard)."""
    try:
        path.relative_to(anchor)
    except ValueError as exc:
        raise ValueError(f"workspace path must be inside {anchor}: {path}") from exc


def _git_root(start: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return Path(root).resolve() if root else None
