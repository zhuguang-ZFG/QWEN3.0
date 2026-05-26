#!/usr/bin/env python3
"""Smoke Brave Search tier when BRAVE_SEARCH_ENABLED=1."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    enabled = os.environ.get("BRAVE_SEARCH_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        print("smoke_ok skip brave (BRAVE_SEARCH_ENABLED=0)")
        return 0

    from search_gateway.brave_adapter import BraveSearchAdapter

    adapter = BraveSearchAdapter.from_env()
    result = adapter.search("FastAPI Depends tutorial", max_results=2)
    if not result.get("ok"):
        print("smoke_fail", result)
        return 1
    count = len(result.get("results") or [])
    print(f"smoke_ok brave results={count}")
    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
