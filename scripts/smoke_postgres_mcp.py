#!/usr/bin/env python3
"""Smoke MCP Postgres server availability (default off)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

_PKG = os.environ.get(
    "LIMA_POSTGRES_MCP_PACKAGE",
    "@modelcontextprotocol/server-postgres",
)


def _npx_cmd() -> str | None:
    return shutil.which("npx") or shutil.which("npx.cmd")


def _database_url() -> str:
    return (
        os.environ.get("LIMA_POSTGRES_MCP_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
        or os.environ.get("POSTGRES_URL", "").strip()
    )


def smoke_start(
    npx: str,
    db_url: str,
    *,
    startup_sec: float = 3.0,
    label: str = "postgres_mcp",
) -> int:
    proc = subprocess.Popen(
        [npx, "-y", _PKG, db_url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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

    enabled = os.environ.get("LIMA_POSTGRES_MCP", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not enabled:
        print("smoke_ok skip postgres_mcp (LIMA_POSTGRES_MCP=0)")
        return 0

    npx = _npx_cmd()
    if not npx:
        print("smoke_fail npx not found")
        return 1

    db_url = _database_url()
    if not db_url:
        print("smoke_ok skip postgres_mcp (no LIMA_POSTGRES_MCP_URL/DATABASE_URL)")
        return 0

    sec = 4.0 if args.live else 2.5
    label = "postgres_mcp_live" if args.live else "postgres_mcp_help"
    return smoke_start(npx, db_url, startup_sec=sec, label=label)


if __name__ == "__main__":
    sys.exit(main())
