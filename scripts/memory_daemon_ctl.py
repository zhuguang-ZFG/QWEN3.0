#!/usr/bin/env python3
"""Inspect or run one LiMa memory daemon cycle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from session_memory.daemon import daemon_status, run_once


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "run-once"))
    parser.add_argument(
        "--no-consolidate",
        action="store_true",
        help="Only ingest inbox files during run-once",
    )
    args = parser.parse_args()

    if args.command == "status":
        payload = daemon_status()
    else:
        payload = run_once(consolidate=not args.no_consolidate)

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
