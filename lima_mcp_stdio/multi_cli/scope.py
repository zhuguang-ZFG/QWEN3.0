"""Infer review scope from task text."""

from __future__ import annotations

import re
from pathlib import Path

_PATH_RE = re.compile(
    r"(?<![\w./-])((?:[\w.-]+/)+[\w.-]+\.(?:py|md|toml|json|ts|tsx|go|rs)|"
    r"(?:routes|tests|docs|src)/[\w_./-]+)(?![\w./-])",
    re.IGNORECASE,
)


def infer_scope_from_task(task: str, project_root: Path) -> str | None:
    hits: list[str] = []
    for match in _PATH_RE.finditer(task):
        rel = match.group(1).replace("\\", "/").strip("./")
        candidate = project_root / rel
        if candidate.is_file() or candidate.is_dir():
            hits.append(rel)
    if not hits:
        return None
    return max(hits, key=len)


def resolve_scope(task: str, scope: str | None, project_root: Path) -> str | None:
    if scope:
        normalized = scope.replace("\\", "/").strip("./")
        candidate = project_root / normalized
        if candidate.is_file() or candidate.is_dir():
            return normalized
        return normalized
    return infer_scope_from_task(task, project_root)
