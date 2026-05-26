#!/usr/bin/env python3
"""Probe Gitee chat models and optionally apply admission overlays (GI-G-3)."""

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

from provider_automation.adapters.gitee_ai import (
    credentials_configured,
    parse_inventory,
    probe_model,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, help="Max models to probe")
    parser.add_argument("--apply", action="store_true", help="Write passing models to backend_admission.json")
    parser.add_argument(
        "--inventory",
        default=str(ROOT / "data" / "gitee_ai_inventory.json"),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "gitee_ai_probe_results.json"),
    )
    args = parser.parse_args()

    if not credentials_configured():
        print("SKIP: GITEE_AI_TOKEN not set", file=sys.stderr)
        return 2

    snap = parse_inventory(args.inventory)
    candidates = [m.model_id for m in snap.models][: max(args.limit, 1)]
    results = [probe_model(model_id) for model_id in candidates]
    passed = [r for r in results if r.get("ok")]

    out = {
        "provider": "gitee",
        "probed": len(results),
        "passed": len(passed),
        "results": results,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    for row in results:
        status = "PASS" if row.get("ok") else row.get("reason", "FAIL")
        print(f"{row['model_id']}: {status}")

    if args.apply and passed:
        from backend_admission_store import load_store, save_store

        data = load_store()
        existing = {o.get("backend_key") for o in data.get("overlays", []) if isinstance(o, dict)}
        for row in passed:
            key = row["backend_key"]
            if key in existing:
                continue
            data.setdefault("overlays", []).append({
                "backend_key": key,
                "provider": "gitee",
                "model_id": row["model_id"],
                "tier": "floor",
                "admission_status": "admitted_late_fallback",
                "private_code_allowed": False,
                "enabled": True,
                "evidence_refs": [str(out_path.name)],
                "latency_ms": float(row.get("latency_ms") or 0.0),
            })
        save_store(data)
        print(f"applied_overlays={len(passed)}")

    print(f"gitee_probe_ok passed={len(passed)}/{len(results)} path={out_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
