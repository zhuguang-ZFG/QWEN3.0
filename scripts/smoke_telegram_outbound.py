#!/usr/bin/env python3
"""Smoke Telegram Bot API outbound via GFW proxy (TG-GH-1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import telegram_outbound as outbound  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send Telegram alert when check fails (best-effort)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip network I/O")
    args = parser.parse_args()

    if args.dry_run:
        print(f"proxies={outbound.proxy_candidates()}")
        return 0

    ok, detail = outbound.check_telegram_getme()
    if ok:
        print(f"OK: {detail}")
        return 0

    print(f"FAIL: {detail}", file=sys.stderr)
    if args.notify:
        try:
            import telegram_notify

            telegram_notify.notify_ops_event(
                f"Telegram outbound smoke FAILED\n{detail}",
                level="critical",
            )
        except Exception as exc:
            print(f"notify error: {type(exc).__name__}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
