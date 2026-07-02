"""Smoke test implementations for Gemini Live and digital-human WebSocket."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import websockets

SMOKE_DIR = Path(__file__).resolve().parent
if str(SMOKE_DIR) not in sys.path:
    sys.path.insert(0, str(SMOKE_DIR))

from config import deploy_config, settings

import ws_ticket_http


LIMA_HOST = deploy_config.VERIFY_HOST


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


async def _test_gemini_live(cfg: dict, api_key: str) -> dict:
    """Run a Gemini Live proxy smoke test."""
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
    device_id = settings.DEVICE.digital_human_default_device_id.strip()
    token = settings.DEVICE.digital_human_default_token.strip()
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
    """Run a digital-human WebSocket smoke test."""
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
