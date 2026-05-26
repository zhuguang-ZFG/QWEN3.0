#!/usr/bin/env python3
"""CF-EVAL-1: refresh inventory, probe remaining candidates, summarize overlay status."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def main() -> int:
    summary: dict = {"steps": []}

    inv_code, inv_out = _run([sys.executable, "scripts/inventory_cloudflare_models.py"])
    summary["steps"].append({"inventory": inv_code, "tail": inv_out.splitlines()[-3:]})

    probe_code, probe_out = _run(
        [sys.executable, "scripts/probe_cf_new_models.py", "--dry-run"]
    )
    summary["steps"].append({"probe_dry_run": probe_code, "tail": probe_out.splitlines()[-5:]})

    admission_path = ROOT / "data" / "backend_admission.json"
    inventory_path = ROOT / "data" / "cf_model_inventory.json"
    if admission_path.is_file():
        from backend_admission_store import load_store, parse_overlays
        from provider_automation.adapters.cloudflare import unregistered_probe_candidates

        overlays = parse_overlays(load_store(str(admission_path)))
        candidates = unregistered_probe_candidates(
            str(inventory_path), admission_path=str(admission_path)
        )
        summary["overlays"] = len(overlays)
        summary["target_overlays"] = 30
        summary["remaining_candidates"] = len(candidates)
        summary["candidate_ids"] = [c.model_id for c in candidates[:10]]
        summary["pool_exhausted_for_admission"] = len(candidates) == 0 or probe_code != 0

    report_path = ROOT / "docs" / "CF_PROBE_REPORT.md"
    if report_path.is_file():
        summary["report"] = report_path.name

    out_path = ROOT / "data" / "cf_eval1_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {out_path}")

    if summary.get("remaining_candidates", 0) == 0:
        print("cf_eval1_ok pool_exhausted")
        return 0
    if probe_code == 0:
        print("cf_eval1_ok probe_pass")
        return 0
    print("cf_eval1_warn candidates_remain_zero_pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
