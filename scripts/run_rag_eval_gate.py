#!/usr/bin/env python3
"""Run offline RAG eval fixtures as a CI gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from context_pipeline.retrieval_eval_runner import (  # noqa: E402
    DEFAULT_CI_FIXTURES,
    run_all_fixture_gates,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        action="append",
        default=[],
        help="Fixture JSON path (repeatable). Defaults to all CI fixtures.",
    )
    args = parser.parse_args()

    fixtures = args.fixture or list(DEFAULT_CI_FIXTURES)
    all_passed, results = run_all_fixture_gates(fixtures)

    for item in results:
        print(item.report)
        print("-" * 40)

    passed_count = sum(1 for item in results if item.passed)
    print(f"RAG gate: {passed_count}/{len(results)} fixtures passed")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
