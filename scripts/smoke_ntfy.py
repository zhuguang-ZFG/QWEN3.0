#!/usr/bin/env python3
"""Smoke ntfy push notification (default off, radar §八)."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request


def _ntfy_url() -> str:
    explicit = os.environ.get("LIMA_NTFY_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    topic = os.environ.get("LIMA_NTFY_TOPIC", "").strip()
    base = os.environ.get("LIMA_NTFY_BASE", "https://ntfy.sh").rstrip("/")
    if topic:
        return f"{base}/{topic}"
    return ""


def smoke_post(url: str, *, title: str, message: str, timeout: float = 12.0) -> int:
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={
            "User-Agent": "LiMa-NtfySmoke/1.0",
            "Title": title,
            "Tags": "white_check_mark",
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
        if 200 <= code < 300:
            print("smoke_ok ntfy_post")
            return 0
        print(f"smoke_fail ntfy_post status={code}")
        return 1
    except urllib.error.HTTPError as exc:
        print(f"smoke_fail ntfy_http_{exc.code}")
        return 1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"smoke_fail ntfy_{type(exc).__name__}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--message",
        default="LiMa ntfy smoke ok",
        help="Notification body",
    )
    args = parser.parse_args()

    enabled = os.environ.get("LIMA_NTFY_SMOKE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not enabled:
        print("smoke_ok skip ntfy (LIMA_NTFY_SMOKE=0)")
        return 0

    url = _ntfy_url()
    if not url:
        print("smoke_ok skip ntfy (no LIMA_NTFY_URL/LIMA_NTFY_TOPIC)")
        return 0

    return smoke_post(url, title="LiMa smoke", message=args.message)


if __name__ == "__main__":
    sys.exit(main())
