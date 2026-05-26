#!/usr/bin/env python3
"""Run full 11-backend coding eval and print summary."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_preflight import check_eval_health
from eval_slice_summary import latest_scores_path, summarize_eval_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Only print summary from latest full JSON",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=11,
        help="Top N backends in summary",
    )
    args = parser.parse_args()

    if not args.skip_run:
        ok, detail = check_eval_health()
        if not ok:
            print(f"eval_preflight_fail {detail}", file=sys.stderr)
            return 2
        print(f"eval_preflight_ok {detail}", flush=True)
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "run_radar_eval_slice.py"),
            "--preflight",
            "--full",
        ]
        print("+", " ".join(cmd), flush=True)
        code = subprocess.call(cmd, cwd=ROOT)
        if code != 0:
            return code

    path = latest_scores_path(ROOT / "data", full=True)
    if not path:
        print("eval_full: no coding_backend_scores_full_*.json", file=sys.stderr)
        return 2
    print(summarize_eval_json(path, top_n=max(1, args.top)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
