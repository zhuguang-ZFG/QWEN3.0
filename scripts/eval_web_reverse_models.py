#!/usr/bin/env python3
"""Run safe admission evals for LiMa web-reverse/local-proxy models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web_reverse_eval import (
    cap_backend_timeouts,
    discover_web_reverse_backends,
    load_inventory,
    safe_web_reverse_cases,
    summarize_results,
    write_json_report,
    write_markdown_report,
)

import http_caller
from backends import BACKENDS
from coding_eval import run_eval

DEFAULT_INVENTORY = ROOT / "data" / "local_reverse_ai_inventory.json"
DEFAULT_JSON = ROOT / "data" / "web_reverse_model_eval.json"
DEFAULT_MD = ROOT / "docs" / "WEB_REVERSE_MODEL_EVAL.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--backends", default="", help="Comma-separated backend names")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--max-backends", type=int, default=0)
    parser.add_argument(
        "--timeout-cap",
        type=int,
        default=0,
        help="Lower selected backend timeouts to this many seconds for broad smoke batches",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    args = parser.parse_args()

    cases = safe_web_reverse_cases()
    if args.max_cases:
        cases = cases[: args.max_cases]

    if args.backends:
        selected = [name.strip() for name in args.backends.split(",") if name.strip()]
    else:
        selected = discover_web_reverse_backends(
            load_inventory(args.inventory), BACKENDS
        )
    if args.max_backends:
        selected = selected[: args.max_backends]

    missing = [name for name in selected if name not in BACKENDS]
    if missing:
        raise SystemExit(f"unknown backend(s): {', '.join(missing)}")

    print("Safety: synthetic public prompts only; no private code context.")
    print(f"Cases: {', '.join(case.id for case in cases)}")
    print(f"Backends ({len(selected)}): {', '.join(selected)}")
    if args.dry_run:
        return 0

    capped = cap_backend_timeouts(BACKENDS, selected, args.timeout_cap)
    if capped:
        print(f"Applied timeout cap to {capped} backend(s): {args.timeout_cap}s")

    results = run_eval(cases, selected, http_caller.call_api)
    summaries = summarize_results(results)
    write_json_report(results, summaries, args.json_out)
    write_markdown_report(results, summaries, args.md_out)
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
