"""Create a redacted SCNet reverse protocol template.

This script accepts a manually captured request JSON and writes a redacted
template. Secrets such as Authorization and Cookie are replaced with
``<redacted>`` and must be supplied later via VPS-only state/env.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reverse_gateway.providers.scnet_protocol import write_redacted_capture


def main() -> int:
    parser = argparse.ArgumentParser(description="Redact a SCNet captured request template")
    parser.add_argument("input", help="Path to captured request JSON")
    parser.add_argument("output", help="Path to write redacted protocol template")
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    template = write_redacted_capture(raw, Path(args.output))
    print(f"wrote redacted SCNet template: {args.output}")
    print(f"endpoint={template.endpoint} stream={template.stream}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
