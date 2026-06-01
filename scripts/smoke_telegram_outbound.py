"""Smoke-check Telegram outbound connectivity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import telegram_outbound


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    proxies = telegram_outbound.proxy_candidates()
    if args.dry_run:
        printable = [proxy or "direct" for proxy in proxies]
        if args.json:
            print(json.dumps({"proxies": printable}, ensure_ascii=False))
        else:
            print(f"proxies={','.join(printable)}")
        return

    ok, detail = telegram_outbound.check_telegram_getme(candidates=proxies)
    if args.json:
        print(json.dumps({"ok": ok, "detail": detail}, ensure_ascii=False))
    else:
        print(f"ok={ok} detail={detail}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
