#!/usr/bin/env python3
"""Smoke Firecrawl MCP server availability (default off)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

_PKG = os.environ.get("LIMA_FIRECRAWL_MCP_PACKAGE", "firecrawl-mcp")


def _npx_cmd() -> str | None:
    return shutil.which("npx") or shutil.which("npx.cmd")


def _firecrawl_env() -> dict[str, str]:
    env = os.environ.copy()
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if key:
        env.setdefault("FIRECRAWL_API_KEY", key)
    url = os.environ.get("FIRECRAWL_API_URL", "").strip()
    if url:
        env.setdefault("FIRECRAWL_API_URL", url)
    return env


def _has_credentials() -> bool:
    return bool(
        os.environ.get("FIRECRAWL_API_KEY", "").strip()
        or os.environ.get("FIRECRAWL_API_URL", "").strip()
    )


def smoke_start(npx: str, *, startup_sec: float = 3.0, label: str = "firecrawl_mcp") -> int:
    proc = subprocess.Popen(
        [npx, "-y", _PKG],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_firecrawl_env(),
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

    enabled = os.environ.get("LIMA_FIRECRAWL_MCP", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not enabled:
        print("smoke_ok skip firecrawl_mcp (LIMA_FIRECRAWL_MCP=0)")
        return 0

    npx = _npx_cmd()
    if not npx:
        print("smoke_fail npx not found")
        return 1

    if not _has_credentials():
        print("smoke_ok skip firecrawl_mcp (no FIRECRAWL_API_KEY/FIRECRAWL_API_URL)")
        return 0

    sec = 4.0 if args.live else 2.5
    label = "firecrawl_mcp_live" if args.live else "firecrawl_mcp_help"
    return smoke_start(npx, startup_sec=sec, label=label)


if __name__ == "__main__":
    sys.exit(main())
