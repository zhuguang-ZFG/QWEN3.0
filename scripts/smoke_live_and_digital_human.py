"""Smoke test for LiMa Gemini Live proxy and digital-human WebSocket.

Uses credentials from `.env` (LIMA_API_KEY, LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN,
etc.) but never prints the raw values.
"""

from __future__ import annotations

import asyncio
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_DIR = Path(__file__).resolve().parent
if str(SMOKE_DIR) not in sys.path:
    sys.path.insert(0, str(SMOKE_DIR))
load_dotenv(PROJECT_ROOT / ".env")

from config import deploy_config, settings
from smoke_live_and_digital_human_tests import _test_digital_human_ws, _test_gemini_live


LIMA_HOST = deploy_config.VERIFY_HOST


def _first_api_key() -> str:
    key = settings.SECURITY.api_key.strip()
    if key:
        return key
    keys = settings.SECURITY.api_keys.strip()
    if keys:
        for k in keys.split(","):
            k = k.strip()
            if k:
                return k
    return ""


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def _https_ctx() -> ssl.SSLContext:
    return ssl.create_default_context()


def _http_get(url: str, api_key: str | None = None) -> tuple[int, str]:
    headers = {"User-Agent": "LiMaSmoke/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_https_ctx(), timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


async def _fetch_live_config(api_key: str) -> dict:
    status, body = _http_get(f"https://{LIMA_HOST}/api/live-key", api_key)
    if status != 200:
        raise RuntimeError(f"/api/live-key returned {status}: {body[:200]}")
    return json.loads(body)


async def main() -> int:
    api_key = _first_api_key()
    if not api_key:
        print("ERROR: LIMA_API_KEY / LIMA_API_KEYS not found in .env")
        return 1
    print(f"Using LiMa API key: {_mask(api_key)}")

    print("\n--- Gemini Live /v1/live proxy ---")
    try:
        cfg = await _fetch_live_config(api_key)
        gemini = await _test_gemini_live(cfg, api_key)
    except Exception as exc:  # noqa: BLE001
        gemini = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if gemini["ok"]:
        print("OK: handshake + audio response succeeded")
        print(f"  model: {gemini['model']}")
        print(f"  setup response keys: {gemini['first_keys']}")
        print(f"  response messages: {gemini['received']}")
    else:
        print(f"FAIL: {gemini['error']}")
        if "first" in gemini:
            print(f"  first response: {gemini['first']}")
        if "received" in gemini:
            print(f"  received: {gemini['received']}")

    print("\n--- Digital human /device/v1/ws ---")
    dh = await _test_digital_human_ws()
    if dh["ok"]:
        print("OK: hello/hello_ack succeeded")
        print(f"  device_id: {dh['device_id']}")
        print(f"  hello_ack keys: {dh['hello_ack_keys']}")
        print(f"  transcript pipeline responses: {dh['pipeline_responses']}")
    else:
        print(f"FAIL: {dh['error']}")
        if "ack" in dh:
            print(f"  ack: {dh['ack']}")

    return 0 if gemini["ok"] and dh["ok"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
