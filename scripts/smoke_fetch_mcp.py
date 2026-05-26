#!/usr/bin/env python3
"""Smoke MCP Fetch server (Python mcp-server-fetch, default off)."""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time


def _module_available() -> bool:
    return importlib.util.find_spec("mcp_server_fetch") is not None


def smoke_help_python() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "mcp_server_fetch", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[:200]
        print("smoke_fail fetch_mcp_help", err)
        return proc.returncode or 1
    print("smoke_ok fetch_mcp_help")
    return 0


def smoke_live_python(*, startup_sec: float = 4.0) -> int:
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server_fetch"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(startup_sec)
        if proc.poll() is None:
            print("smoke_ok fetch_mcp_live")
            return 0
        print("smoke_fail fetch_mcp_live exited_early code=%s" % proc.returncode)
        return proc.returncode or 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def smoke_help_npx(npx: str, package: str) -> int:
    proc = subprocess.run(
        [npx, "-y", package, "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[:200]
        print("smoke_fail fetch_mcp_npx_help", err)
        return proc.returncode or 1
    print("smoke_ok fetch_mcp_npx_help")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Briefly spawn fetch MCP server",
    )
    args = parser.parse_args()

    enabled = os.environ.get("LIMA_FETCH_MCP", "0").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        print("smoke_ok skip fetch_mcp (LIMA_FETCH_MCP=0)")
        return 0

    use_npx = os.environ.get("LIMA_FETCH_MCP_USE_NPX", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if use_npx:
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if not npx:
            print("smoke_fail npx not found")
            return 1
        pkg = os.environ.get(
            "LIMA_FETCH_MCP_PACKAGE",
            "@modelcontextprotocol/server-fetch",
        )
        code = smoke_help_npx(npx, pkg)
        return code

    if not _module_available():
        print("smoke_fail mcp_server_fetch not installed (pip install mcp-server-fetch)")
        return 1

    if args.live:
        code = smoke_help_python()
        if code != 0:
            return code
        return smoke_live_python()
    return smoke_help_python()


if __name__ == "__main__":
    sys.exit(main())
