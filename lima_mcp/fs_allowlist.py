"""Filesystem access control — path allowlist enforcement for MCP file tools.

All file operations must pass through `validate_path()` which enforces:
  1. Path must be within one of the configured allowed roots.
  2. Symlinks are resolved before checking.
  3. Traversal attempts (../) are rejected.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

_log = logging.getLogger(__name__)


def _default_allowed_roots() -> list[str]:
    """Build default allowed roots from env or workspace layout."""
    env_val = os.getenv("LIMA_FILESYSTEM_ALLOWED_ROOTS", "").strip()
    if env_val:
        return [p.strip() for p in env_val.split(os.pathsep) if p.strip()]

    roots: list[str] = []
    cwd = os.getcwd()

    # Allow the current working directory
    roots.append(cwd)

    # Allow explicit project roots from env
    for key in ("LIMA_PROJECT_ROOT", "LIMA_ROOT", "LIMA_WORKSPACE"):
        val = os.getenv(key, "").strip()
        if val and os.path.isdir(val) and val not in roots:
            roots.append(val)

    return roots


def _load_allowed_roots() -> list[Path]:
    """Load and resolve allowed roots. Cached after first call."""
    return [Path(r).resolve() for r in _default_allowed_roots()]


def is_within_allowed(path: str | Path) -> bool:
    """Check if a path is within at least one allowed root."""
    allowed = _load_allowed_roots()
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError):
        return False
    for root in allowed:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def validate_path(requested: str, *, must_exist: bool = True) -> tuple[bool, Path | str]:
    """Validate a user-requested path against the allowlist.

    Returns (ok, resolved_path_or_error_message).
    """
    if not requested or not requested.strip():
        return False, "empty path"

    raw = requested.strip()

    # Reject traversal markers early
    if ".." in raw.replace("\\", "/").split("/"):
        return False, "path traversal rejected"

    try:
        candidate = Path(raw).resolve()
    except (OSError, ValueError) as exc:
        _log.warning("Path resolution failed: %s (%s)", raw, exc)
        return False, f"invalid path: {exc}"

    if must_exist and not candidate.exists():
        return False, f"path not found: {raw}"

    if not is_within_allowed(candidate):
        _log.warning("Path outside allowlist: %s", candidate)
        return False, f"path outside allowed workspace: {raw}"

    return True, candidate
