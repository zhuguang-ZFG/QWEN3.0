#!/usr/bin/env python3
"""Smoke Playwright MCP availability for LC-W Verify (default off)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def main() -> int:
    enabled = os.environ.get("LIMA_PLAYWRIGHT_MCP", "0").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        print("smoke_ok skip playwright (LIMA_PLAYWRIGHT_MCP=0)")
        return 0

    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print("smoke_fail npx not found")
        return 1

    proc = subprocess.run(
        [npx, "-y", "@playwright/mcp@latest", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        print("smoke_fail playwright_mcp_help", proc.stderr[:200])
        return proc.returncode
    print("smoke_ok playwright_mcp_help")
    return 0


if __name__ == "__main__":
    sys.exit(main())
