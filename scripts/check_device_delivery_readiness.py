"""P0-3 preflight: cloud readiness for device WSS delivery (no hardware required).

Usage:
  python scripts/check_device_delivery_readiness.py --base-url http://127.0.0.1:8081
  python scripts/check_device_delivery_readiness.py --base-url https://chat.donglicao.com \\
      --device-id dev1 --device-token secret
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _get(url: str, timeout: float = 10.0) -> tuple[int, dict | str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body


def _post_json(url: str, payload: dict, headers: dict[str, str], timeout: float = 10.0) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body


def check_local_env(*, base_url: str = "") -> list[str]:
    """Return list of problem strings for local process env (not remote VPS env)."""
    problems: list[str] = []
    env = os.environ.get("LIMA_RUNTIME_ENV", "").strip().lower()
    fallback = os.environ.get("LIMA_WS_REGISTERED_DEVICE_FALLBACK", "0").strip() in {"1", "true", "yes", "on"}
    allow = os.environ.get("LIMA_WS_FALLBACK_ALLOW_PRODUCTION", "0").strip() in {"1", "true", "yes", "on"}
    public_base = base_url.startswith("https://") and "127.0.0.1" not in base_url and "localhost" not in base_url
    if not env:
        msg = "WARN: LIMA_RUNTIME_ENV unset (production VPS must set LIMA_RUNTIME_ENV=production)"
        if public_base:
            msg = (
                "WARN: LIMA_RUNTIME_ENV unset while probing a public URL — "
                "this script only sees *local* env; SSH the VPS and require LIMA_RUNTIME_ENV=production"
            )
        problems.append(msg)
    if fallback and env == "production" and not allow:
        problems.append(
            "local env: LIMA_WS_REGISTERED_DEVICE_FALLBACK=1 forbidden in production without "
            "LIMA_WS_FALLBACK_ALLOW_PRODUCTION=1"
        )
    elif fallback and env == "production" and allow:
        problems.append("WARN: production allows empty-token WS fallback (temporary only)")
    elif fallback:
        problems.append("WARN: LIMA_WS_REGISTERED_DEVICE_FALLBACK=1 (prefer LIMA_DEVICE_TOKENS)")
    tokens = os.environ.get("LIMA_DEVICE_TOKENS", "").strip()
    if not tokens:
        problems.append("WARN: LIMA_DEVICE_TOKENS empty (ticket auth needs device_id=token pairs)")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Device delivery readiness preflight (P0-3)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8081", help="DLC base URL")
    parser.add_argument("--device-id", default="", help="Optional device_id for ticket probe")
    parser.add_argument("--device-token", default="", help="Optional device token for ticket probe")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    exit_code = 0

    print("== local env (not remote VPS) ==")
    for line in check_local_env(base_url=base):
        print(" ", line)
        if line.startswith("local env:"):
            exit_code = 1

    print("== health ==")
    status, body = _get(f"{base}/health")
    print(f"  GET /health -> {status} {body}")
    if status != 200:
        exit_code = 1

    if args.device_id and args.device_token:
        print("== ticket ==")
        code, ticket_body = _post_json(
            f"{base}/device/v1/ws/ticket",
            {"device_id": args.device_id},
            {"Authorization": f"Bearer {args.device_token}"},
        )
        print(f"  POST /device/v1/ws/ticket -> {code} {ticket_body}")
        if code != 200 or not isinstance(ticket_body, dict) or not ticket_body.get("ticket"):
            exit_code = 1
    else:
        print("== ticket == (skip: pass --device-id and --device-token)")

    print("== next (hardware) ==")
    print("  1) Device: wss://…/device/v1/ws?ticket=… then hello")
    print("  2) Dispatch draw/write; expect dispatchStatus=sent when online")
    print("  3) Record evidence per docs/DEVICE_E2E_CHECKLIST_CN.md")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
