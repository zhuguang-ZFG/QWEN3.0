#!/usr/bin/env python3
"""Fetch Gitee 模力方舟 model inventory (GI-G-3)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from provider_automation.adapters.gitee_ai import credentials_configured, fetch_models, parse_inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "gitee_ai_inventory.json"),
        help="JSON output path",
    )
    args = parser.parse_args()

    if not credentials_configured():
        print("SKIP: GITEE_AI_TOKEN not set", file=sys.stderr)
        return 2

    inventory = fetch_models()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    snap = parse_inventory(out_path)
    print(f"gitee_ai_inventory_ok models={inventory['model_count']} chat_candidates={len(snap.models)} path={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
