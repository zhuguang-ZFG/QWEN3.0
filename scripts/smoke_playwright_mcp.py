#!/usr/bin/env python3
"""Smoke Playwright MCP availability for LC-W Verify (default off)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time


def _npx_cmd() -> str | None:
    return shutil.which("npx") or shutil.which("npx.cmd")


def smoke_help(npx: str) -> int:
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


def smoke_live(npx: str, *, startup_sec: float = 4.0) -> int:
    ver = subprocess.run(
        [npx, "playwright", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    if ver.returncode != 0:
        print("smoke_fail playwright_cli", (ver.stderr or ver.stdout)[:200])
        return ver.returncode or 1

    proc = subprocess.Popen(
        [npx, "-y", "@playwright/mcp@latest"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(startup_sec)
        if proc.poll() is None:
            print("smoke_ok playwright_mcp_live")
            return 0
        print("smoke_fail playwright_mcp_live exited_early code=%s" % proc.returncode)
        return proc.returncode or 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Spawn @playwright/mcp briefly (requires Node + npx)",
    )
    args = parser.parse_args()

    enabled = os.environ.get("LIMA_PLAYWRIGHT_MCP", "0").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        print("smoke_ok skip playwright (LIMA_PLAYWRIGHT_MCP=0)")
        return 0

    npx = _npx_cmd()
    if not npx:
        print("smoke_fail npx not found")
        return 1

    if args.live:
        code = smoke_help(npx)
        if code != 0:
            return code
        return smoke_live(npx)
    return smoke_help(npx)


if __name__ == "__main__":
    sys.exit(main())
