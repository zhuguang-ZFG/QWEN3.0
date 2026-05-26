"""Run deptry unused-dependency scan (radar §四)."""

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
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Exit 0 even when deptry finds issues (CI report mode)",
    )
    args = parser.parse_args()

    cmd = [
        sys.executable,
        "-m",
        "deptry",
        *[str(ROOT / p) if not p.endswith(".py") else str(ROOT / p) for p in SCAN_PATHS],
        "--requirements-files",
        "requirements_server.txt",
        "--ignore",
        "DEP002,DEP003",
    ]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    if proc.returncode == 0:
        print("deptry: clean")
        return 0
    if args.report_only:
        print(f"deptry: findings reported (exit {proc.returncode}, report-only)")
        return 0
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
