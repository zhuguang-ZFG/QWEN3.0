"""Workspace resolution for global MiMo MCP (any git project)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def resolve_workspace(explicit: str | None = None) -> Path:
    """Pick project root: explicit arg > MIMO_MCP_WORKSPACE > git root > cwd."""
    if explicit and explicit.strip():
        return Path(explicit.strip()).expanduser().resolve()
    env = os.environ.get("MIMO_MCP_WORKSPACE", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    cwd = Path.cwd().resolve()
    git_root = _git_root(cwd)
    return git_root or cwd


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
