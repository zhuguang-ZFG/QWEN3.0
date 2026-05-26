#!/usr/bin/env python3
"""CLI: optional /health pre-check then Healthchecks.io dead-man ping (INF-B)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import healthcheck_ping as hc  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ping-url",
        default="",
        help="Healthchecks ping URL (or use --env-key)",
    )
    parser.add_argument(
        "--env-key",
        default="HEALTHCHECK_LIMA_VPS_URL",
        help="Env var holding ping URL when --ping-url omitted",
    )
    parser.add_argument(
        "--check",
        default="",
        help="Optional health URL to verify before ping (e.g. http://127.0.0.1:8080/health)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ping even when LIMA_HEALTHCHECK_ENABLED=0",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved config without network I/O",
    )
    args = parser.parse_args()

    enabled = True if args.force else None
    ping_url = hc.resolve_ping_url(args.ping_url, env_key=args.env_key)
    health_url = args.check.strip() or None

    if args.dry_run:
        print(f"enabled={hc.is_healthcheck_enabled() if enabled is None else enabled}")
        print(f"env_key={args.env_key}")
        print(f"ping_url={ping_url or '(empty)'}")
        print(f"health_url={health_url or '(none)'}")
        return 0

    return hc.check_then_ping(
        health_url=health_url,
        ping_url=ping_url,
        env_key="" if args.ping_url else args.env_key,
        enabled=enabled,
    )


if __name__ == "__main__":
    raise SystemExit(main())
