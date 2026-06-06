#!/usr/bin/env python3
"""Build free web AI admission reports from registry and probe results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from free_web_ai_admission import build_admission, write_json, write_markdown

DEFAULT_REGISTRY = ROOT / "data" / "free_web_ai_candidates.json"
DEFAULT_PROBES = ROOT / "data" / "free_web_ai_probe_results.json"
DEFAULT_JSON = ROOT / "data" / "free_web_ai_admission.json"
DEFAULT_MD = ROOT / "docs" / "FREE_WEB_AI_ADMISSION.md"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--probes", default=str(DEFAULT_PROBES))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    args = parser.parse_args()

    candidates = _read_json(Path(args.registry), [])
    probes = _read_json(Path(args.probes), [])
    decisions = build_admission(candidates, probes)
    write_json(args.json_out, decisions)
    write_markdown(args.md_out, decisions)
    print(f"Wrote {args.json_out} and {args.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
