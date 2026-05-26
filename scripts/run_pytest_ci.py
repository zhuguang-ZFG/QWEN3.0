#!/usr/bin/env python3
"""CI pytest entry: parallel workers + coverage report (no fail-under gate yet)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-xdist",
        action="store_true",
        help="Run without pytest-xdist (single process)",
    )
    parser.add_argument(
        "--no-cov",
        action="store_true",
        help="Skip coverage collection",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Extra args after -- (e.g. -- -k test_foo)",
    )
    args = parser.parse_args()
    extra = [a for a in args.pytest_args if a != "--"]

    cmd = [sys.executable, "-m", "pytest", "-q"]
    if not args.no_xdist:
        cmd.extend(["-n", "auto", "--dist", "loadscope"])
    if not args.no_cov:
        cmd.extend(["--cov", "--cov-report=term-missing:skip-covered"])
    cmd.extend(extra)

    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
