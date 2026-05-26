#!/usr/bin/env python3
"""Run all radar MCP smoke scripts (default-off skip mode)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_MCP_SMOKES: tuple[tuple[str, str], ...] = (
    ("fetch", "scripts/smoke_fetch_mcp.py"),
    ("filesystem", "scripts/smoke_filesystem_mcp.py"),
    ("github", "scripts/smoke_github_mcp.py"),
    ("postgres", "scripts/smoke_postgres_mcp.py"),
    ("brave", "scripts/smoke_brave_mcp.py"),
    ("firecrawl", "scripts/smoke_firecrawl_mcp.py"),
    ("playwright", "scripts/smoke_playwright_mcp.py"),
)


def _run_one(name: str, script: str, *, live: bool) -> tuple[int, str]:
    cmd = [sys.executable, str(ROOT / script)]
    if live:
        cmd.append("--live")
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    line = (proc.stdout or proc.stderr or "").strip().splitlines()
    detail = line[-1] if line else f"exit={proc.returncode}"
    return proc.returncode, detail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Pass --live to each MCP smoke script",
    )
    args = parser.parse_args()

    failed = 0
    print("mcp_gates inventory (LIMA_*_MCP=0 → skip expected)")
    for name, script in _MCP_SMOKES:
        code, detail = _run_one(name, script, live=args.live)
        mark = "ok" if code == 0 else "FAIL"
        print(f"  [{mark}] {name}: {detail}")
        if code != 0:
            failed += 1

    if failed:
        print(f"mcp_gates_fail count={failed}")
        return 1
    print("mcp_gates_ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
