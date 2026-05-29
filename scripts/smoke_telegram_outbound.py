#!/usr/bin/env python3
"""Smoke test for Telegram outbound connectivity (dry-run mode)."""
import os
import sys

def main():
    dry_run = "--dry-run" in sys.argv

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    proxies = {
        "http": os.environ.get("HTTP_PROXY", ""),
        "https": os.environ.get("HTTPS_PROXY", ""),
    }
    proxy_count = sum(1 for v in proxies.values() if v)

    print(f"bot_token={'set' if bot_token else 'MISSING'}")
    print(f"chat_id={'set' if chat_id else 'MISSING'}")
    print(f"proxies={proxy_count}")

    if dry_run:
        print("DRY RUN — no messages sent")
        return

    if not bot_token or not chat_id:
        print("ERROR: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        sys.exit(1)

if __name__ == "__main__":
    main()
