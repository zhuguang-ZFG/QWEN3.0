#!/usr/bin/env python3
"""Probe unregistered Cloudflare chat models and update backend_admission.json (CF-G-2)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend_admission_store import load_store, overlay_from_probe, parse_overlays, upsert_overlay
from provider_automation.adapters.cloudflare import (
    cf_credentials_configured,
    make_coding_callable,
    make_smoke_callable,
    unregistered_probe_candidates,
)
from provider_automation.catalog import ModelAdmissionStatus
from provider_automation.runner import ProbeRunner, ProbeRunnerConfig, format_batch_results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", default=str(ROOT / "data" / "cf_model_inventory.json"))
    parser.add_argument("--admission", default=str(ROOT / "data" / "backend_admission.json"))
    parser.add_argument("--limit", type=int, default=0, help="Max candidates (0 = all remaining)")
    parser.add_argument("--target-overlays", type=int, default=30,
                        help="Stop applying after this many total overlays (50%% of ~60 unregistered)")
    parser.add_argument("--dry-run", action="store_true", help="Probe only; do not write admission")
    parser.add_argument("--apply", action="store_true", help="Write passing models to admission overlay")
    parser.add_argument(
        "--completion-only",
        action="store_true",
        help="Skip coding fixture; metadata + completion smoke only (SANDBOX overlay tier)",
    )
    args = parser.parse_args()

    if not cf_credentials_configured():
        print("SKIP: CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_TOKEN not set", file=sys.stderr)
        return 2

    candidates = unregistered_probe_candidates(args.inventory, admission_path=args.admission)
    if not candidates:
        current = len(parse_overlays(load_store(args.admission)))
        print(f"no remaining probe candidates (overlays={current})")
        return 0

    current_overlays = len(parse_overlays(load_store(args.admission)))
    need = max(0, args.target_overlays - current_overlays)
    cap = args.limit if args.limit > 0 else len(candidates)
    if need > 0:
        cap = min(cap, need + 5)
    candidates = candidates[: max(1, cap)]

    print(
        f"probing {len(candidates)} CF candidate(s) "
        f"(overlays {current_overlays}/{args.target_overlays})..."
    )
    runner = ProbeRunner(ProbeRunnerConfig(
        run_metadata=True,
        run_completion_smoke=True,
        run_coding_fixture=not args.completion_only,
    ))
    runner.set_smoke_callable(make_smoke_callable())
    runner.set_coding_callable(make_coding_callable())

    results = runner.run(candidates)
    report_md = format_batch_results(results)
    report_path = ROOT / "docs" / "CF_PROBE_REPORT.md"
    report_path.write_text(
        "# CF Probe Report\n\n"
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n"
        f"Mode: {'completion-only' if args.completion_only else 'metadata+completion+coding'}\n\n"
        + report_md + "\n",
        encoding="utf-8",
    )
    print(f"report: {report_path}")

    json_path = ROOT / "data" / "cf_probe_results.json"
    json_path.write_text(
        json.dumps([
            {
                "model_id": r.model.model_id,
                "final_status": r.final_status.value,
                "highest_level": r.highest_level_passed.value,
                "capabilities": r.model.capabilities,
            }
            for r in results
        ], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    admitted = 0
    if args.apply and not args.dry_run:
        current_overlays = len(parse_overlays(load_store(args.admission)))
        for batch in results:
            if current_overlays + admitted >= args.target_overlays:
                break
            overlay = overlay_from_probe(batch.model, batch)
            if overlay is None:
                continue
            upsert_overlay(overlay, args.admission)
            admitted += 1
            print(f"admitted overlay: {overlay.backend_key} tier={overlay.tier}")

    passed = sum(
        1 for r in results
        if r.final_status in (ModelAdmissionStatus.CANDIDATE, ModelAdmissionStatus.SANDBOX_ONLY)
    )
    print(f"probe_ok passed={passed}/{len(results)} admitted={admitted}")
    return 0 if passed > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
