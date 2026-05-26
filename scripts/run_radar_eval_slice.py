#!/usr/bin/env python3
"""Radar P2-4: coding backend eval slice (dry-run or quick/full run)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Limit to 3 backends and 2 cases (smoke eval)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List cases/backends only",
    )
    parser.add_argument(
        "--backends",
        default="",
        help="Comma-separated backend override",
    )
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d")
    json_out = ROOT / "data" / f"coding_backend_scores_{stamp}.json"
    md_out = ROOT / "docs" / "CODING_BACKEND_RANKING.md"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "eval_coding_backends.py"),
        "--json-out",
        str(json_out),
        "--md-out",
        str(md_out),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.quick:
        cmd.extend(["--max-backends", "3", "--max-cases", "2"])
    if args.backends:
        cmd.extend(["--backends", args.backends])

    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
