#!/usr/bin/env python3
"""Run CF-G-0 inventory for Cloudflare + Google and write diff report."""

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

from provider_inventory.cloudflare import credentials_configured as cf_ready
from provider_inventory.cloudflare import fetch_cloudflare_models
from provider_inventory.compare import compare_inventory, format_inventory_report
from provider_inventory.weekly_diff import compute_weekly_diff
from provider_inventory.google import credentials_configured as google_ready
from provider_inventory.google import fetch_google_models


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cf-json", default=str(ROOT / "data" / "cf_model_inventory.json"))
    parser.add_argument("--google-json", default=str(ROOT / "data" / "google_model_inventory.json"))
    parser.add_argument("--report", default=str(ROOT / "docs" / "CF_GOOGLE_INVENTORY_REPORT.md"))
    parser.add_argument("--offline", action="store_true", help="Only regenerate report from existing JSON")
    args = parser.parse_args()

    cf_inventory = None
    cf_diff = None
    google_inventory = None
    google_diff = None
    exit_code = 0

    if not args.offline:
        if cf_ready():
            try:
                cf_inventory = fetch_cloudflare_models()
                Path(args.cf_json).write_text(
                    json.dumps(cf_inventory, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"cf models={cf_inventory['model_count']}")
            except Exception as exc:
                exit_code = 1
                print(f"cloudflare fetch failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        else:
            print("cloudflare skipped: missing credentials", file=sys.stderr)

        if google_ready():
            try:
                google_inventory = fetch_google_models()
                Path(args.google_json).write_text(
                    json.dumps(google_inventory, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"google models={google_inventory['model_count']}")
            except Exception as exc:
                exit_code = 1
                print(f"google fetch failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        else:
            print("google skipped: missing credentials", file=sys.stderr)

    cf_path = Path(args.cf_json)
    if cf_inventory is None and cf_path.is_file():
        cf_inventory = json.loads(cf_path.read_text(encoding="utf-8"))
    if cf_inventory:
        cf_diff = compare_inventory(cf_inventory, backend_prefixes=("cf_", "cfai_"))

    google_path = Path(args.google_json)
    if google_inventory is None and google_path.is_file():
        google_inventory = json.loads(google_path.read_text(encoding="utf-8"))
    if google_inventory:
        google_diff = compare_inventory(google_inventory, backend_prefixes=("google_",))

    report = format_inventory_report(cf_inventory, cf_diff, google_inventory, google_diff)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"report written: {report_path}")

    if cf_diff:
        print(
            f"cf unregistered={len(cf_diff.get('unregistered_remote', []))} "
            f"registered={cf_diff.get('registered_backend_count', 0)}"
        )
    if google_diff:
        print(
            f"google unregistered={len(google_diff.get('unregistered_remote', []))} "
            f"registered={google_diff.get('registered_backend_count', 0)}"
        )

    if cf_inventory or google_inventory:
        weekly = compute_weekly_diff(cf_inventory, google_inventory)
        cf_w = weekly.get("cloudflare") or {}
        google_w = weekly.get("google") or {}
        print(
            f"weekly_diff cf_added={len(cf_w.get('added', []))} "
            f"google_added={len(google_w.get('added', []))}"
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
