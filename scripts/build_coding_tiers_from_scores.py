#!/usr/bin/env python3
"""Rebuild data/coding_backend_tiers.json from existing coding_backend_scores.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coding_pool_admission import build_tiers_from_eval_results, write_tier_assignments


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scores",
        default=str(ROOT / "data" / "coding_backend_scores.json"),
        help="Path to eval scores JSON array",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "data" / "coding_backend_tiers.json"),
        help="Output tier assignments path",
    )
    args = parser.parse_args()

    scores_path = Path(args.scores)
    if not scores_path.is_file():
        raise SystemExit(f"scores file not found: {scores_path}")

    rows = json.loads(scores_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("scores file must be a JSON array")

    assignments = build_tiers_from_eval_results(rows)
    out = write_tier_assignments(
        assignments,
        path=Path(args.out),
        source="coding_backend_scores",
    )
    print(f"Wrote {out} ({len(assignments)} backends)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
