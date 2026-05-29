"""Subprocess helpers for gate/smoke tests (Windows-safe UTF-8 decode)."""

from __future__ import annotations

import subprocess
from typing import Any


def run_script(
    cmd: list[str],
    *,
    cwd: str,
    timeout: float | int,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a script with UTF-8 text mode; replace undecodable bytes on Windows."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        **kwargs,
    )
