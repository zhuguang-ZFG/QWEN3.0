#!/usr/bin/env python3
"""Ship lima-router journal lines to OpenObserve (PE-C-2)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from observability.openobserve_sink import _config, post_records


def _fetch_journal(since: str, limit: int) -> list[dict]:
    cmd = [
        "journalctl",
        "-u",
        "lima-router",
        "--since",
        since,
        "-n",
        str(limit),
        "-o",
        "json",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except FileNotFoundError:
        return []
    records: list[dict] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append(
            {
                "source": "journal",
                "unit": row.get("_SYSTEMD_UNIT", "lima-router"),
                "message": str(row.get("MESSAGE", ""))[:2000],
                "priority": row.get("PRIORITY"),
                "timestamp": row.get("__REALTIME_TIMESTAMP"),
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="1 hour ago")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = _fetch_journal(args.since, args.limit)
    print(f"journal_lines={len(records)}")
    if not records:
        print("ship_skip=no journal lines (local Windows or empty unit)")
        print("smoke_ok")
        return 0

    cfg = _config()
    cfg = dict(cfg)
    cfg["stream"] = os.environ.get("OPENOBSERVE_JOURNAL_STREAM", "lima_journal")

    if args.dry_run:
        print(json.dumps(records[:2], ensure_ascii=False)[:400])
        print("dry_run_ok")
        return 0

    ok = post_records(records, cfg=cfg)
    print("ship_ok" if ok else "ship_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
