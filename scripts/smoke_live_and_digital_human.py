"""Smoke test for LiMa Gemini Live proxy and digital-human WebSocket.

Uses credentials from `.env` (LIMA_API_KEY, LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN,
etc.) but never prints the raw values.
"""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

import websockets
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_DIR = Path(__file__).resolve().parent
if str(SMOKE_DIR) not in sys.path:
    sys.path.insert(0, str(SMOKE_DIR))
load_dotenv(PROJECT_ROOT / ".env")

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


def _build_gemini_ws_url(cfg: dict, api_key: str) -> tuple[str, str]:
    """Resolve model and authenticated WebSocket URL from live config."""
    url = cfg.get("url", "/v1/live")
    model = cfg.get("model", "models/gemini-2.0-flash-live-001")
    ws_url = f"wss://{LIMA_HOST}{url}" if url.startswith("/") else url
    ticket = ws_ticket_http.issue_chat_ws_ticket(LIMA_HOST, api_key)
    return ws_ticket_http.ws_url_with_ticket(ws_url, ticket), model


async def _send_gemini_setup(ws, model: str) -> dict:
    """Send setup message and wait for setupComplete; returns {ok, first_obj?}."""
    await ws.send(
        json.dumps(
            {
                "setup": {
                    "model": model,
                    "generationConfig": {"responseModalities": ["AUDIO"]},
                }
            }
        )
    )
    first = await asyncio.wait_for(ws.recv(), timeout=15)
    first_obj = json.loads(first)
    if "setupComplete" not in first_obj:
        return {
            "ok": False,
            "error": f"expected setupComplete, got: {first_obj.keys()}",
            "first": first_obj,
        }
    return {"ok": True, "first_obj": first_obj}


def _summarize_gemini_message(obj: dict) -> str:
    """Summarize a single Gemini Live response message."""
    if "serverContent" in obj:
        parts = obj.get("serverContent", {}).get("modelTurn", {}).get("parts", [])
        return f"serverContent parts={len(parts)} types={[list(p.keys()) for p in parts]}"
    if obj.get("setupComplete"):
        return "setupComplete"
    return str(list(obj.keys()))


async def _run_gemini_conversation(ws) -> list[str]:
    """Send a prompt and collect audio/text responses until audio/timeout."""
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
    received: list[str] = []
    try:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=20)
            if isinstance(msg, bytes):
                received.append(f"<binary audio {len(msg)} bytes>")
                break
            obj = json.loads(msg)
            received.append(_summarize_gemini_message(obj))
            if "serverContent" in obj and any(
                "inlineData" in p for p in obj.get("serverContent", {}).get("modelTurn", {}).get("parts", [])
            ):
                break
    except asyncio.TimeoutError:
        received.append("<no audio response within 20s>")
    return received


def _build_gemini_error(exc: Exception) -> dict:
    """Normalize Gemini Live errors into a result dict."""
    if isinstance(exc, websockets.exceptions.InvalidStatus):
        return {"ok": False, "error": f"WebSocket handshake failed: {exc.status_code}"}
    if isinstance(exc, asyncio.TimeoutError):
        return {"ok": False, "error": "timeout waiting for Gemini response"}
    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _test_gemini_live(api_key: str) -> dict:
    cfg = await _fetch_live_config(api_key)
    if not cfg.get("available"):
        return {"ok": False, "error": f"/api/live-key says unavailable: {cfg}"}

    ws_url, model = _build_gemini_ws_url(cfg, api_key)
    try:
        async with websockets.connect(ws_url, additional_headers={"User-Agent": "LiMaSmoke/1.0"}) as ws:
            setup = await _send_gemini_setup(ws, model)
            if not setup["ok"]:
                return setup
            received = await _run_gemini_conversation(ws)
            return {
                "ok": any("binary audio" in r or "inlineData" in r for r in received),
                "model": model,
                "first_keys": list(setup["first_obj"].keys()),
                "received": received,
            }
    except Exception as exc:  # noqa: BLE001
        return _build_gemini_error(exc)


def _load_digital_human_creds() -> tuple[str, str, str | None]:
    """Return (device_id, token, error_or_none)."""
    device_id = os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID", "").strip()
    token = os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN", "").strip()
    if not token:
        return "", "", "LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN not set; supply a device token in .env"
    return device_id or "web-tester", token, None


async def _connect_digital_human_ws(device_id: str, token: str):
    """Open a WebSocket to the digital-human endpoint."""
    ticket = ws_ticket_http.issue_device_ws_ticket(LIMA_HOST, device_id, token)
    ws_url = ws_ticket_http.ws_url_with_ticket(f"wss://{LIMA_HOST}/device/v1/ws", ticket)
    return await websockets.connect(ws_url, additional_headers={"User-Agent": "LiMaSmoke/1.0"})


async def _send_hello(ws, device_id: str) -> dict:
    """Send hello and wait for hello_ack; returns {ok, ack_obj?}."""
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
        return {"ok": False, "error": f"expected hello_ack, got {ack_obj.get('type')}", "ack": ack_obj}
    return {"ok": True, "ack_obj": ack_obj}


def _summarize_digital_human_response(obj: dict) -> str:
    """Summarize a single response message for logging."""
    summary = obj.get("type", "unknown")
    if obj.get("type") == "voice_status":
        summary = f"voice_status({obj.get('status')}, transcript={obj.get('transcript', '')[:40]!r})"
    elif obj.get("type") == "error":
        summary = f"error({obj.get('code')}: {obj.get('message')})"
    return summary


async def _run_transcript_pipeline(ws, device_id: str) -> list[str]:
    """Send a transcript and collect pipeline responses until audio/error/timeout."""
    await ws.send(json.dumps({"type": "transcript", "device_id": device_id, "text": "你好，请简短介绍一下自己。"}))
    responses: list[str] = []
    try:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=60)
            if isinstance(msg, bytes):
                responses.append(f"<binary audio chunk {len(msg)} bytes>")
                break
            obj = json.loads(msg)
            responses.append(_summarize_digital_human_response(obj))
            if obj.get("type") in ("audio_reply", "error"):
                break
    except asyncio.TimeoutError:
        responses.append("<no further response within 60s>")
    return responses


def _build_digital_human_error(exc: Exception) -> dict:
    """Normalize WebSocket / timeout / other errors into a result dict."""
    if isinstance(exc, websockets.exceptions.InvalidStatus):
        return {"ok": False, "error": f"WebSocket handshake failed: {exc.status_code}"}
    if isinstance(exc, asyncio.TimeoutError):
        return {"ok": False, "error": "timeout waiting for hello_ack"}
    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _test_digital_human_ws() -> dict:
    device_id, token, error = _load_digital_human_creds()
    if error:
        return {"ok": False, "error": error}

    try:
        async with await _connect_digital_human_ws(device_id, token) as ws:
            hello = await _send_hello(ws, device_id)
            if not hello["ok"]:
                return hello
            responses = await _run_transcript_pipeline(ws, device_id)
            return {
                "ok": True,
                "device_id": device_id,
                "hello_ack_keys": list(hello["ack_obj"].keys()),
                "pipeline_responses": responses,
            }
    except Exception as exc:  # noqa: BLE001
        return _build_digital_human_error(exc)


async def main() -> int:
    api_key = _first_api_key()
    if not api_key:
        print("ERROR: LIMA_API_KEY / LIMA_API_KEYS not found in .env")
        return 1
    print(f"Using LiMa API key: {_mask(api_key)}")

    print("\n--- Gemini Live /v1/live proxy ---")
    gemini = await _test_gemini_live(api_key)
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
