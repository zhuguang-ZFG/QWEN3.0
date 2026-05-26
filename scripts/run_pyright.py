"""Run pyright type check (radar §四, report-only)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCAN_PATHS = (
    "routes",
    "search_gateway",
    "channel_gateway",
    "context_pipeline",
    "agent_runtime",
    "eval_preflight.py",
    "periodic_coding_eval.py",
    "routing_engine.py",
    "smart_router.py",
    "http_caller.py",
    "server.py",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Exit 0 even when pyright reports issues",
    )
    args = parser.parse_args()

    targets = [str(ROOT / p) for p in SCAN_PATHS]
    cmd = [sys.executable, "-m", "pyright", *targets, "--level", "warning"]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    if proc.returncode == 0:
        print("pyright: clean")
        return 0
    if args.report_only:
        print(f"pyright: findings reported (exit {proc.returncode}, report-only)")
        return 0
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
