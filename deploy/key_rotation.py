#!/usr/bin/env python3
"""Deprecated key rotation daemon (P0.3).

The legacy implementation exposed raw API keys on localhost:8909 without auth.
It is archived at scripts/archive/key_rotation_legacy.py for reference only.
Do not run this script in production.
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "deploy/key_rotation.py is retired. "
        "See scripts/archive/key_rotation_legacy.py and "
        "docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md (P0.3).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
