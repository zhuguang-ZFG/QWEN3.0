#!/usr/bin/env python3
"""Smoke Brave Search MCP server (official @brave package, default off)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

_PKG = os.environ.get(
    "LIMA_BRAVE_MCP_PACKAGE",
    "@brave/brave-search-mcp-server",
)


def _npx_cmd() -> str | None:
    return shutil.which("npx") or shutil.which("npx.cmd")


def _brave_env() -> dict[str, str]:
    env = os.environ.copy()
    key = (
        os.environ.get("BRAVE_API_KEY", "").strip()
        or os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    )
    if key:
        env.setdefault("BRAVE_API_KEY", key)
    return env


def smoke_start(npx: str, *, startup_sec: float = 3.0, label: str = "brave_mcp") -> int:
    proc = subprocess.Popen(
        [npx, "-y", _PKG, "--transport", "stdio"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_brave_env(),
    )
    try:
        time.sleep(startup_sec)
        if proc.poll() is None:
            print(f"smoke_ok {label}")
            return 0
        print(f"smoke_fail {label} exited_early code={proc.returncode}")
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
        help="Keep server up slightly longer before terminate",
    )
    args = parser.parse_args()

    enabled = os.environ.get("LIMA_BRAVE_MCP", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not enabled:
        print("smoke_ok skip brave_mcp (LIMA_BRAVE_MCP=0)")
        return 0

    npx = _npx_cmd()
    if not npx:
        print("smoke_fail npx not found")
        return 1

    sec = 4.0 if args.live else 2.5
    label = "brave_mcp_live" if args.live else "brave_mcp_help"
    return smoke_start(npx, startup_sec=sec, label=label)


if __name__ == "__main__":
    sys.exit(main())
