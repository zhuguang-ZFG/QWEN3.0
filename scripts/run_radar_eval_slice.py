#!/usr/bin/env python3
"""Radar P2-4: coding backend eval slice (dry-run or quick/full run)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_preflight import check_eval_health, full_backend_list, quick_backend_list


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Limit to 3 backends and 2 cases (smoke eval)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="11 SCNet/Kimi backends and all coding cases (~3min)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List cases/backends only",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Require LiMa /health before live eval",
    )
    parser.add_argument(
        "--backends",
        default="",
        help="Comma-separated backend override",
    )
    args = parser.parse_args()

    if args.preflight:
        ok, detail = check_eval_health()
        if not ok:
            print(f"eval_preflight_fail {detail}", flush=True)
            return 2
        print(f"eval_preflight_ok {detail}", flush=True)
        try:
            from eval_topology import eval_via_router_url, topology_status_lines

            url = eval_via_router_url()
            if url:
                print(f"eval_topology via_router={url}", flush=True)
            for line in topology_status_lines():
                print(f"eval_topology {line}", flush=True)
        except ImportError:
            pass

    stamp = datetime.now().strftime("%Y%m%d")
    suffix = "_full" if args.full else ""
    json_out = ROOT / "data" / f"coding_backend_scores{suffix}_{stamp}.json"
    md_out = ROOT / "docs" / "CODING_BACKEND_RANKING.md"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "eval_coding_backends.py"),
        "--json-out",
        str(json_out),
        "--md-out",
        str(md_out),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.quick:
        cmd.extend(["--max-backends", "3", "--max-cases", "2"])
    backends = args.backends.strip()
    if not backends and args.quick:
        backends = ",".join(quick_backend_list())
    elif not backends and args.full:
        backends = ",".join(full_backend_list())
    if backends:
        cmd.extend(["--backends", backends])

    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
