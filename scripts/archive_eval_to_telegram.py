#!/usr/bin/env python3
"""Archive latest eval summary to Telegram operator chat (LIMA_TG_ARCHIVE=1)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_slice_summary import latest_scores_path, summarize_eval_json
from telegram_archive import archive_enabled, archive_text_async


async def _main_async(*, full: bool, top: int, chat_id: str) -> int:
    if not archive_enabled():
        print("archive_skip LIMA_TG_ARCHIVE=0")
        return 0

    path = latest_scores_path(ROOT / "data", full=full)
    if not path:
        print("archive_fail no eval json", file=sys.stderr)
        return 2

    body = summarize_eval_json(path, top_n=max(1, top))
    label = f"eval-{'full' if full else 'quick'}:{path.name}"
    ok = await archive_text_async(label, body, chat_id=chat_id, parse_mode="")
    if ok:
        print(f"archive_ok {path.name}")
        return 0
    print("archive_fail send", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Archive full-11 eval JSON")
    parser.add_argument("--top", type=int, default=11, help="Backends in summary")
    parser.add_argument("--chat-id", default="", help="Override TELEGRAM_CHAT_ID")
    args = parser.parse_args()
    return asyncio.run(
        _main_async(full=args.full, top=args.top, chat_id=args.chat_id.strip())
    )


if __name__ == "__main__":
    sys.exit(main())
