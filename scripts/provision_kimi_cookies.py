"""Provision Kimi cookies into a private state file.

The input is a browser cookie export JSON array (from EditThisCookie or similar).
The output path must be a private runtime path on the VPS and must never be
committed to git.

Usage:
  python scripts/provision_kimi_cookies.py D:/QWEN3.0/kimi.txt /opt/lima-router/reverse_gateway_state/kimi_cookies.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from typing import Any

from reverse_gateway.providers.scnet_cookie import CookieState, load_cookie_state

KIMI_DEFAULT_PATH = "/opt/lima-router/reverse_gateway_state/kimi_cookies.json"
KIMI_PUBLIC_COOKIE_NAMES = {"theme", "language", "_tea_utm_cache_20001731"}
REDACTED = "<redacted>"


def write_kimi_cookie_state(raw: list[dict[str, Any]], path: Path) -> CookieState:
    """Write Kimi cookies to a private state file and return the state."""
    filtered = []
    for cookie in raw:
        if not isinstance(cookie, dict):
            continue
        name = str(cookie.get("name") or "")
        if not name:
            continue
        # Keep only essential fields to avoid cluttering the state file
        filtered.append({
            "name": name,
            "value": str(cookie.get("value") or ""),
            "domain": str(cookie.get("domain") or ""),
            "path": str(cookie.get("path") or "/"),
            "httpOnly": bool(cookie.get("httpOnly")),
            "secure": bool(cookie.get("secure")),
            "sameSite": cookie.get("sameSite"),
        })
    state = CookieState(cookies=tuple(filtered))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(filtered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return state


def redact_kimi_cookies(cookies: list[dict]) -> list[dict]:
    """Redact sensitive values for logging/health display."""
    redacted = []
    for cookie in cookies:
        item = dict(cookie)
        name = str(item.get("name") or "").lower()
        if name not in KIMI_PUBLIC_COOKIE_NAMES:
            item["value"] = REDACTED
        redacted.append(item)
    return redacted


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Kimi browser cookies")
    parser.add_argument("input", help="Browser cookie export JSON (e.g. from EditThisCookie)")
    parser.add_argument(
        "output",
        nargs="?",
        default=KIMI_DEFAULT_PATH,
        help=f"Private runtime cookie state path (default: {KIMI_DEFAULT_PATH})",
    )
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("input must be a cookie JSON array (browser export format)")

    state = write_kimi_cookie_state(raw, Path(args.output))
    reloaded = load_kimi_state(Path(args.output))

    # Print summary (redacted —- no secrets in output)
    auth_cookie = None
    for c in state.cookies:
        cn = str(c.get("name") or "")
        if cn in ("kimi-auth", "Token", "jsessionid"):
            auth_cookie = cn
            break

    print(f"wrote {len(state.cookies)} Kimi cookies to {args.output}")
    print(f"auth_cookie: {auth_cookie or 'NOT FOUND — check export'}")
    if reloaded:
        print(f"cookie_header_len={len(reloaded.cookie_header())}")
    else:
        print("WARNING: reload verification failed")

    # Check for critical auth cookie
    has_auth = any(
        str(c.get("name") or "") in ("kimi-auth", "Token", "jsessionid")
        for c in state.cookies
    )
    if not has_auth:
        print("WARNING: No kimi-auth/Token/jsessionid cookie found — login may be broken")
        return 1
    return 0


def load_kimi_state(path: Path) -> CookieState | None:
    """Load Kimi cookie state for verification (reuses SCNet loader)."""
    return load_cookie_state(path)


if __name__ == "__main__":
    raise SystemExit(main())
