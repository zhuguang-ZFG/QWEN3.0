#!/usr/bin/env python3
"""Smoke Telegram archive gate (default off)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from telegram_archive import archive_enabled, chunk_text, format_archive_message


def main() -> int:
    if not archive_enabled():
        print("smoke_ok skip tg_archive (LIMA_TG_ARCHIVE=0)")
        return 0

    sample = format_archive_message("smoke", "x" * 5000)
    parts = chunk_text(sample)
    if not parts or len(parts) < 2:
        print("smoke_fail tg_archive chunk")
        return 1
    print(f"smoke_ok tg_archive chunks={len(parts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
