#!/usr/bin/env python3
"""Smoke MCP GitHub server availability (default off)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

_PKG = os.environ.get(
    "LIMA_GITHUB_MCP_PACKAGE",
    "@modelcontextprotocol/server-github",
)


def _npx_cmd() -> str | None:
    return shutil.which("npx") or shutil.which("npx.cmd")


def _github_env() -> dict[str, str]:
    env = os.environ.copy()
    token = (
        os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or ""
    ).strip()
    if token:
        env.setdefault("GITHUB_PERSONAL_ACCESS_TOKEN", token)
    return env


def smoke_start(npx: str, *, startup_sec: float = 3.0, label: str = "github_mcp") -> int:
    proc = subprocess.Popen(
        [npx, "-y", _PKG],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_github_env(),
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

    enabled = os.environ.get("LIMA_GITHUB_MCP", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not enabled:
        print("smoke_ok skip github_mcp (LIMA_GITHUB_MCP=0)")
        return 0

    npx = _npx_cmd()
    if not npx:
        print("smoke_fail npx not found")
        return 1

    sec = 4.0 if args.live else 2.5
    label = "github_mcp_live" if args.live else "github_mcp_help"
    return smoke_start(npx, startup_sec=sec, label=label)


if __name__ == "__main__":
    sys.exit(main())
