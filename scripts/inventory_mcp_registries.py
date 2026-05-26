#!/usr/bin/env python3
"""Fetch MCP registry inventory from official + Glama + SafeMCP (PE-A-1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from provider_inventory.mcp_registries import build_mcp_registry_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "mcp_registry_snapshot.json"),
        help="JSON output path",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print summary only")
    parser.add_argument("--official-pages", type=int, default=20)
    parser.add_argument("--glama-pages", type=int, default=50)
    args = parser.parse_args()

    snapshot = build_mcp_registry_snapshot(
        official_page_limit=max(1, args.official_pages),
        glama_page_limit=max(1, args.glama_pages),
    )
    counts = snapshot.get("counts") or {}
    merged = int(counts.get("merged") or 0)
    if merged < 1:
        print("mcp_inventory_FAILED: no merged entries", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps({"counts": counts, "sources": snapshot.get("sources")}, indent=2))
        return 0

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"mcp_inventory_ok merged={merged} "
        f"official={counts.get('official')} glama={counts.get('glama')} "
        f"safemcp={counts.get('safemcp')} path={out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
