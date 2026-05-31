"""Small command-safety helpers for operator-triggered subprocesses."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Collection

SHELL_META_CHARS = frozenset("|&;<>`")


class UnsafeCommandError(ValueError):
    """Raised when a command string requires shell semantics or is not allowed."""


def parse_safe_command(command: str, allowed_commands: Collection[str]) -> list[str]:
    """Parse a command into argv and reject shell syntax.

    This intentionally supports simple command lines only. Operators that need
    pipes or redirection should add a reviewed wrapper command instead of
    passing shell syntax through chat/task inputs.
    """
    stripped = command.strip()
    if not stripped:
        raise UnsafeCommandError("empty command")
    if any(ch in stripped for ch in SHELL_META_CHARS) or "\n" in stripped or "\r" in stripped:
        raise UnsafeCommandError("shell metacharacters are not allowed")
    try:
        argv = shlex.split(stripped, posix=True)
    except ValueError as exc:
        raise UnsafeCommandError(f"invalid command quoting: {exc}") from exc
    if not argv:
        raise UnsafeCommandError("empty command")

    executable = Path(argv[0]).name.lower()
    allowed = {name.lower() for name in allowed_commands}
    if executable not in allowed:
        raise UnsafeCommandError(f"command not allowed: {executable}")
    return argv


def run_safe_command(
    command: str,
    *,
    allowed_commands: Collection[str],
    timeout: int,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a reviewed simple command with ``shell=False``."""
    argv = parse_safe_command(command, allowed_commands)
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd, check=False)
