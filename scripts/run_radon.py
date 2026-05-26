"""Run radon cyclomatic complexity report (radar §四, report-only)."""

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
        help="Exit 0 even when radon reports high complexity",
    )
    parser.add_argument(
        "--min-grade",
        default="B",
        help="Minimum acceptable grade (default B)",
    )
    args = parser.parse_args()

    targets = [str(ROOT / p) if not p.endswith(".py") else str(ROOT / p) for p in SCAN_PATHS]
    cmd = [
        sys.executable,
        "-m",
        "radon",
        "cc",
        *targets,
        "-a",
        "-nc",
        f"--min={args.min_grade}",
    ]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    if proc.returncode == 0:
        print("radon: clean")
        return 0
    if args.report_only:
        print(f"radon: findings reported (exit {proc.returncode}, report-only)")
        return 0
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
