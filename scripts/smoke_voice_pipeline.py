"""Smoke test for the self-hosted /v1/voice pipeline.

Uses credentials from `.env` (LIMA_API_KEY) but never prints the raw value.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

import websockets
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SMOKE_DIR = Path(__file__).resolve().parent
if str(SMOKE_DIR) not in sys.path:
    sys.path.insert(0, str(SMOKE_DIR))

import ws_ticket_http

LIMA_HOST = os.environ.get("LIMA_VERIFY_HOST", "chat.donglicao.com")


def _first_api_key() -> str:
    key = os.environ.get("LIMA_API_KEY", "").strip()
    if key:
        return key
    keys = os.environ.get("LIMA_API_KEYS", "").strip()
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


async def _test_text_pipeline(api_key: str) -> dict:
    ticket = ws_ticket_http.issue_chat_ws_ticket(LIMA_HOST, api_key)
    url = ws_ticket_http.ws_url_with_ticket(f"wss://{LIMA_HOST}/v1/voice", ticket)
    try:
        async with websockets.connect(url, additional_headers={"User-Agent": "LiMaSmoke/1.0"}) as ws:
            await ws.send(json.dumps({"type": "text", "text": "你好，请简短介绍一下自己。"}))
            messages: list[str] = []
            audio_bytes = 0
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=60)
                if isinstance(msg, bytes):
                    audio_bytes += len(msg)
                    messages.append(f"<binary audio {len(msg)} bytes>")
                    break
                obj = json.loads(msg)
                msg_type = obj.get("type", "unknown")
                if msg_type == "status":
                    messages.append(f"status({obj.get('status')}, {obj.get('transcript', '')[:40]!r})")
                elif msg_type == "transcript":
                    messages.append(f"transcript({obj.get('text', '')[:40]!r})")
                elif msg_type == "reply":
                    messages.append(f"reply({obj.get('text', '')[:80]!r})")
                elif msg_type == "audio":
                    data = obj.get("data", "")
                    audio_bytes += len(base64.b64decode(data)) if data else 0
                    messages.append(f"audio(base64 {len(data)} chars)")
                    break
                elif msg_type == "error":
                    return {"ok": False, "error": f"{obj.get('code')}: {obj.get('message')}", "messages": messages}
            return {"ok": bool(audio_bytes), "messages": messages}
    except websockets.exceptions.InvalidStatus as exc:
        return {"ok": False, "error": f"WebSocket handshake failed: {exc.status_code}"}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "timeout waiting for voice pipeline response"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def main() -> int:
    api_key = _first_api_key()
    if not api_key:
        print("ERROR: LIMA_API_KEY / LIMA_API_KEYS not found in .env")
        return 1
    print(f"Using LiMa API key: {_mask(api_key)}")

    print("\n--- /v1/voice text pipeline ---")
    result = await _test_text_pipeline(api_key)
    if result["ok"]:
        print("OK: /v1/voice text → reply → audio succeeded")
        for m in result["messages"]:
            print(" ", m)
    else:
        print(f"FAIL: {result['error']}")
        for m in result.get("messages", []):
            print(" ", m)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
