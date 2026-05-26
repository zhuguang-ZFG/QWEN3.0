#!/usr/bin/env python3
"""Compare GitHub vs Gitee mirror HEAD SHA (GI-G-5)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gitee_mirror import compare_mirror_heads


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--branch", default="", help="Branch name (default: HEAD)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = compare_mirror_heads(args.repo, args.branch or "HEAD")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not result.get("ok"):
        print(f"mirror_lag_check_FAILED: {result.get('error', 'unknown')}")
    elif result.get("in_sync"):
        print(f"mirror_lag_ok branch={result.get('branch')} sha={result.get('github_sha')}")
    else:
        print(
            f"mirror_lag_DRIFT github={result.get('github_sha')} "
            f"gitee={result.get('gitee_sha')}"
        )
    return 0 if result.get("ok") and result.get("in_sync") else 1


if __name__ == "__main__":
    raise SystemExit(main())
