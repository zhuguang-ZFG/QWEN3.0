#!/usr/bin/env python3
"""TG-GH-2 smoke: LiMa Code worker Telegram lifecycle notifier (dry-run or --send)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    token = os.environ.get("LIMA_CODE_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("SKIP: LIMA_CODE_TELEGRAM_BOT_TOKEN missing", file=sys.stderr)
        return 2

    tsx = ROOT / "deepcode-cli" / "node_modules" / ".bin" / "tsx.cmd"
    if not tsx.is_file():
        tsx = ROOT / "deepcode-cli" / "node_modules" / ".bin" / "tsx"
    if not tsx.is_file():
        print("FAIL: deepcode-cli tsx missing", file=sys.stderr)
        return 1

    verify = ROOT / "scripts" / "verify_tg_gh2_limacode_telegram.ts"
    args = [str(tsx), str(verify)]
    if "--send" in sys.argv:
        args.append("--send")

    proc = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, check=False)
    lines = (proc.stdout or "").strip().splitlines()
    last = lines[-1] if lines else ""
    try:
        payload = json.loads(last)
    except json.JSONDecodeError:
        err = (proc.stderr or proc.stdout or "")[:300]
        print(f"FAIL: {err}", file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("smoke_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
