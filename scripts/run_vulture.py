#!/usr/bin/env python3
"""Run Vulture dead-code scan (radar §四, report-only by default)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCAN_PATHS = (
    "routes",
    "search_gateway",
    "lima_mcp",
    "channel_gateway",
    "tool_gateway",
    "context_pipeline",
    "session_memory",
    "agent_runtime",
    "observability",
    "device_gateway",
    "gitee_webhook",
    "routing_engine.py",
    "smart_router.py",
    "http_caller.py",
    "server.py",
)

EXCLUDE = "venv,.venv,esp32S_XYZ,deepcode-cli,wechat_bridge,scripts/archive,tests"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Exit 0 even when vulture finds dead code",
    )
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=80,
        help="Minimum confidence 0-100 (default 80)",
    )
    args = parser.parse_args()

    targets = [str(ROOT / p) for p in SCAN_PATHS]
    cmd = [
        sys.executable,
        "-m",
        "vulture",
        *targets,
        "--exclude",
        EXCLUDE,
        f"--min-confidence={args.min_confidence}",
    ]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    if proc.returncode == 0:
        print("vulture: clean")
        return 0
    if args.report_only:
        print(f"vulture: findings reported (exit {proc.returncode}, report-only)")
        return 0
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
