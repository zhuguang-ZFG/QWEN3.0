#!/usr/bin/env python3
"""Print summary of latest coding-backend eval JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_slice_summary import latest_scores_path, summarize_eval_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Use latest full-11 eval JSON",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Top N backends in summary",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Explicit JSON path (overrides --full)",
    )
    args = parser.parse_args()

    path = args.path
    if path is None:
        path = latest_scores_path(ROOT / "data", full=args.full)
    if path is None or not path.is_file():
        label = "full" if args.full else "quick"
        print(f"eval_report: no {label} scores JSON in data/", file=sys.stderr)
        return 2

    print(summarize_eval_json(path, top_n=max(1, args.top)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
