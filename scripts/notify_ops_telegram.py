#!/usr/bin/env python3
"""Send ops/deploy/smoke notification to Telegram (TG-GH-6). Run on VPS with .env loaded."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _send(message: str, event_type: str) -> int:
    message = (message or "").strip()
    if not message:
        return 1
    try:
        import telegram_notify
    except ImportError:
        print("notify_skip telegram_notify missing", file=sys.stderr)
        return 2
    if event_type == "smoke":
        telegram_notify.notify_smoke_event(message)
    elif event_type == "deploy":
        telegram_notify.notify_deploy_event(message)
    else:
        telegram_notify.notify_ops_event(message, level="warning")
    print("notify_ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", default="")
    parser.add_argument("--type", choices=("deploy", "smoke", "ops"), default="ops")
    parser.add_argument("--b64", default="", help="base64 JSON {message,type}")
    args = parser.parse_args()

    if args.b64:
        try:
            data = json.loads(base64.b64decode(args.b64.encode("ascii")))
        except Exception as exc:
            print(f"notify_bad_payload {type(exc).__name__}", file=sys.stderr)
            return 1
        return _send(str(data.get("message") or ""), str(data.get("type") or args.type))
    return _send(args.message, args.type)


if __name__ == "__main__":
    raise SystemExit(main())
