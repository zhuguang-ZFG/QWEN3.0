#!/usr/bin/env python3
"""Run LiMa personal coding-backend evals."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import http_caller
from backends import BACKENDS
from coding_eval import (
    candidate_backends,
    load_cases,
    run_eval,
    write_json_report,
    write_markdown_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", default=str(ROOT / "evals" / "coding_cases"))
    parser.add_argument("--backends", default="", help="Comma-separated backend names")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--max-backends", type=int, default=0)
    parser.add_argument("--include-unconfigured", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-out", default=str(ROOT / "data" / "coding_backend_scores.json"))
    parser.add_argument("--md-out", default=str(ROOT / "docs" / "CODING_BACKEND_RANKING.md"))
    args = parser.parse_args()

    cases = load_cases(args.case_dir)
    if args.max_cases:
        cases = cases[: args.max_cases]

    if args.backends:
        selected = [b.strip() for b in args.backends.split(",") if b.strip()]
    else:
        selected = candidate_backends(
            BACKENDS, include_unconfigured=args.include_unconfigured
        )
    if args.max_backends:
        selected = selected[: args.max_backends]

    missing = [b for b in selected if b not in BACKENDS]
    if missing:
        raise SystemExit(f"unknown backend(s): {', '.join(missing)}")

    print(f"Cases: {', '.join(c.id for c in cases)}")
    print(f"Backends ({len(selected)}): {', '.join(selected)}")
    if args.dry_run:
        return 0

    results = run_eval(cases, selected, http_caller.call_api)
    write_json_report(results, args.json_out)
    write_markdown_report(results, args.md_out)
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
