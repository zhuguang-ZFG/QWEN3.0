#!/usr/bin/env python3
"""Smoke SearXNG adapter (PE-D-1) — skips gracefully when disabled or unreachable."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from search_gateway.searxng_adapter import SearXNGAdapter, searxng_enabled


def main() -> int:
    enabled = searxng_enabled()
    base = os.environ.get("SEARXNG_BASE_URL", "http://127.0.0.1:8081")
    print(f"enabled={enabled} base_url={base}")

    if not enabled:
        print("searxng_skip=SEARXNG_ENABLED=0 (expected default)")
        print("smoke_ok")
        return 0

    adapter = SearXNGAdapter.from_env()
    result = adapter.search("FastAPI Depends documentation", max_results=3)
    print(f"search_ok={result.get('ok')} error={result.get('error', '')}")
    if result.get("ok"):
        for row in (result.get("results") or [])[:3]:
            print(f"  - {row.get('source')} {row.get('title', '')[:60]}")
        print("smoke_ok")
        return 0

    print("smoke_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
