"""Smoke test for LiMa Gemini Live proxy and digital-human WebSocket.

Uses credentials from `.env` (LIMA_API_KEY, LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN,
etc.) but never prints the raw values.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

import websockets
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


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


def _extract_digital_human_value(html: str, key: str) -> str:
    """Extract a default value injected by the patched index page."""
    if key == "token":
        match = re.search(r'<input\s+[^>]*id="limaToken"\s+[^>]*value="([^"]*)"', html)
        return (match.group(1) if match else "").strip()
    # Values set via the inline JS use setInput("<id>", "<value>").
    match = re.search(rf'setInput\("{re.escape(key)}",\s*"([^"]*)"\)', html)
    return (match.group(1) if match else "").strip()


async def _fetch_live_config(api_key: str) -> dict:
    status, body = _http_get(f"https://{LIMA_HOST}/api/live-key", api_key)
    if status != 200:
        raise RuntimeError(f"/api/live-key returned {status}: {body[:200]}")
    return json.loads(body)


async def _test_gemini_live(api_key: str) -> dict:
    cfg = await _fetch_live_config(api_key)
    if not cfg.get("available"):
        return {"ok": False, "error": f"/api/live-key says unavailable: {cfg}"}

    url = cfg.get("url", "/v1/live")
    model = cfg.get("model", "models/gemini-2.0-flash-live-001")
    if url.startswith("/"):
        proto = "wss"
        ws_url = f"{proto}://{LIMA_HOST}{url}"
    else:
        ws_url = url
    ws_url += ("&" if "?" in ws_url else "?") + f"authorization=Bearer {api_key}"

    try:
        async with websockets.connect(ws_url, additional_headers={"User-Agent": "LiMaSmoke/1.0"}) as ws:
            await ws.send(
                json.dumps(
                    {
                        "setup": {
                            "model": model,
                            "generationConfig": {"responseModalities": ["TEXT"]},
                        }
                    }
                )
            )
            first = await asyncio.wait_for(ws.recv(), timeout=15)
            first_obj = json.loads(first)
            if not first_obj.get("setupComplete"):
                return {
                    "ok": False,
                    "error": f"expected setupComplete, got: {first_obj.keys()}",
                    "first": first_obj,
                }

            await ws.send(
                json.dumps(
                    {
                        "clientContent": {
                            "turns": [{"role": "user", "parts": [{"text": "Hello, can you hear me?"}]}],
                            "turnComplete": True,
                        }
                    }
                )
            )
            second = await asyncio.wait_for(ws.recv(), timeout=20)
            second_obj = json.loads(second)
            text_parts = []
            for part in second_obj.get("serverContent", {}).get("modelTurn", {}).get("parts", []):
                if "text" in part:
                    text_parts.append(part["text"])
            return {
                "ok": bool(text_parts),
                "model": model,
                "first_keys": list(first_obj.keys()),
                "text": text_parts,
                "raw_keys": list(second_obj.keys()),
            }
    except websockets.exceptions.InvalidStatus as exc:
        return {"ok": False, "error": f"WebSocket handshake failed: {exc.status_code}"}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "timeout waiting for Gemini response"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _test_digital_human_ws() -> dict:
    device_id = os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID", "").strip()
    token = os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN", "").strip()
    token_source = "env"

    if not token:
        # The patched digital-human page injects defaults; these values are
        # already delivered to browsers, so parsing them is a fair fallback.
        status, body = _http_get(f"https://{LIMA_HOST}/digital-human/")
        if status != 200:
            return {"ok": False, "error": f"digital-human page returned {status}"}
        token = _extract_digital_human_value(body, "token")
        if not token:
            return {"ok": False, "error": "could not extract default token from digital-human page"}
        if not device_id:
            device_id = _extract_digital_human_value(body, "deviceMac")
        token_source = "page"

    if not device_id:
        device_id = "web-tester"

    ws_url = f"wss://{LIMA_HOST}/device/v1/ws?authorization=Bearer {token}"
    try:
        async with websockets.connect(ws_url, additional_headers={"User-Agent": "LiMaSmoke/1.0"}) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "hello",
                        "protocol": "lima-device-v1",
                        "device_id": device_id,
                        "fw_rev": "smoke-test",
                        "capabilities": ["audio", "text_chat"],
                    }
                )
            )
            ack = await asyncio.wait_for(ws.recv(), timeout=10)
            ack_obj = json.loads(ack)
            if ack_obj.get("type") != "hello_ack":
                return {
                    "ok": False,
                    "error": f"expected hello_ack, got {ack_obj.get('type')}",
                    "ack": ack_obj,
                }

            # Try a text transcript to see if the LLM+TTS pipeline responds.
            await ws.send(
                json.dumps(
                    {
                        "type": "transcript",
                        "device_id": device_id,
                        "text": "你好，请简短介绍一下自己。",
                    }
                )
            )
            responses: list[str] = []
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=60)
                    if isinstance(msg, bytes):
                        responses.append(f"<binary audio chunk {len(msg)} bytes>")
                        break
                    obj = json.loads(msg)
                    summary = obj.get("type", "unknown")
                    if obj.get("type") == "voice_status":
                        summary = f"voice_status({obj.get('status')}, transcript={obj.get('transcript','')[:40]!r})"
                    elif obj.get("type") == "error":
                        summary = f"error({obj.get('code')}: {obj.get('message')})"
                    responses.append(summary)
                    if obj.get("type") == "audio_reply":
                        break
                    if obj.get("type") == "error":
                        break
            except asyncio.TimeoutError:
                responses.append("<no further response within 60s>")

            return {
                "ok": True,
                "device_id": device_id,
                "token_source": token_source,
                "hello_ack_keys": list(ack_obj.keys()),
                "pipeline_responses": responses,
            }
    except websockets.exceptions.InvalidStatus as exc:
        return {"ok": False, "error": f"WebSocket handshake failed: {exc.status_code}"}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "timeout waiting for hello_ack"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def main() -> int:
    api_key = _first_api_key()
    if not api_key:
        print("ERROR: LIMA_API_KEY / LIMA_API_KEYS not found in .env")
        return 1
    print(f"Using LiMa API key: {_mask(api_key)}")

    print("\n--- Gemini Live /v1/live proxy ---")
    gemini = await _test_gemini_live(api_key)
    if gemini["ok"]:
        print("OK: handshake + text response succeeded")
        print(f"  model: {gemini['model']}")
        print(f"  setup response keys: {gemini['first_keys']}")
        print(f"  response text preview: {gemini['text'][:120] if gemini['text'] else '(empty)'}")
    else:
        print(f"FAIL: {gemini['error']}")
        if "first" in gemini:
            print(f"  first response: {gemini['first']}")
        if "raw_keys" in gemini:
            print(f"  raw keys: {gemini['raw_keys']}")

    print("\n--- Digital human /device/v1/ws ---")
    dh = await _test_digital_human_ws()
    if dh["ok"]:
        print("OK: hello/hello_ack succeeded")
        print(f"  device_id: {dh['device_id']}")
        print(f"  token_source: {dh.get('token_source', 'unknown')}")
        print(f"  hello_ack keys: {dh['hello_ack_keys']}")
        print(f"  transcript pipeline responses: {dh['pipeline_responses']}")
    else:
        print(f"FAIL: {dh['error']}")
        if "ack" in dh:
            print(f"  ack: {dh['ack']}")

    return 0 if gemini["ok"] and dh["ok"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
