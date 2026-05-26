#!/usr/bin/env python3
"""Smoke Apprise multi-channel notify (default off, radar §八)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notify.apprise_bridge import apprise_urls, notify


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--message",
        default="LiMa Apprise smoke ok",
        help="Notification body",
    )
    parser.add_argument(
        "--title",
        default="LiMa smoke",
        help="Notification title",
    )
    args = parser.parse_args()

    enabled = os.environ.get("LIMA_APPRISE_SMOKE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not enabled:
        print("smoke_ok skip apprise (LIMA_APPRISE_SMOKE=0)")
        return 0

    urls = apprise_urls()
    if not urls:
        print("smoke_ok skip apprise (no LIMA_APPRISE_URLS)")
        return 0

    ok, detail = notify(args.message, title=args.title, urls=urls)
    if ok:
        print(f"smoke_ok apprise sent channels={len(urls)}")
        return 0
    if detail == "apprise_not_installed":
        print("smoke_ok skip apprise (pip install apprise)")
        return 0
    print(f"smoke_fail apprise {detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
