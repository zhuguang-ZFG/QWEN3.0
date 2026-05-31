"""Provision SCNet cookies into a private state file.

The input is a browser cookie export JSON array. The output path must be a
private runtime path such as `/opt/lima-router/reverse_gateway_state` and must
never be committed to git.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reverse_gateway.providers.scnet_cookie import load_cookie_state, write_cookie_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision SCNet browser cookies")
    parser.add_argument("input", help="Browser cookie export JSON")
    parser.add_argument("output", help="Private runtime cookie state path")
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("input must be a cookie JSON array")
    state = write_cookie_state(raw, Path(args.output))
    reloaded = load_cookie_state(Path(args.output))
    print(f"wrote {len(state.cookies)} SCNet cookies to {args.output}")
    print(f"cookie_header_len={len(reloaded.cookie_header()) if reloaded else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
