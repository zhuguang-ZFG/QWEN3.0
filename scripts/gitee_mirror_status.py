#!/usr/bin/env python3
"""Report git remotes and mirror readiness (GI-G-0)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gitee_mirror import collect_mirror_status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(ROOT), help="Git repo path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    status = collect_mirror_status(args.repo)
    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        if not status.get("ok"):
            print(f"ERROR: {status.get('error')}", file=sys.stderr)
        else:
            print(f"remotes={status.get('remote_count')} github={status.get('has_github')} gitee={status.get('has_gitee')}")
            for remote in status.get("remotes", []):
                print(f"  {remote['name']} ({remote['host']}) push={remote['push']}")
    return 0 if status.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
