"""Production E2E probes for device-app voice (REST + WebSocket)."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Callable

from voice_e2e_http import (
    fake_wav_bytes,
    get_json,
    post_json,
    post_multipart,
    probe_pcm_chunks,
    probe_transcript_ok,
    probe_wav_bytes,
)

VOICE_TRANSCRIBE_PATH = "/device/v1/app/voice/transcribe"
VOICE_TICKET_PATH = "/device/v1/app/voice/ticket"
AUTH_ME_PATH = "/device/v1/app/auth/me"
AUTH_LOGIN_PATH = "/device/v1/app/auth/login"
LEGACY_VOICE_WS_PATH = "/v1/voice"
APP_VOICE_WS_PATH = "/device/v1/app/voice/ws"


@dataclass(frozen=True)
class ProbeResult:
    name: str
    status: str
    message: str


def voice_e2e_strict() -> bool:
    return os.environ.get("LIMA_VOICE_E2E_STRICT", "").strip().lower() in {"1", "true", "yes"}


def voice_e2e_skipped() -> bool:
    return os.environ.get("LIMA_VOICE_E2E_SKIP", "").strip().lower() in {"1", "true", "yes"}


def resolve_device_app_token(host: str) -> tuple[str | None, str]:
    """Return (bearer_token, source_label) or (None, reason)."""
    token = os.environ.get("LIMA_VERIFY_DEVICE_APP_TOKEN", "").strip()
    if token:
        return token, "env:LIMA_VERIFY_DEVICE_APP_TOKEN"
    code = os.environ.get("LIMA_VERIFY_WECHAT_CODE", "").strip()
    if not code:
        return None, "missing LIMA_VERIFY_DEVICE_APP_TOKEN or LIMA_VERIFY_WECHAT_CODE"
    status, body = post_json(host, AUTH_LOGIN_PATH, {"code": code})
    if status != 200:
        return None, f"wechat login returned {status}: {body}"
    jwt = str(body.get("token") or "").strip()
    if not jwt:
        return None, f"wechat login missing token: {body}"
    return jwt, "wechat:LIMA_VERIFY_WECHAT_CODE"


def probe_voice_transcribe_unauth(host: str) -> ProbeResult:
    status, _body = post_multipart(
        host,
        VOICE_TRANSCRIBE_PATH,
        files={"audio": ("clip.wav", fake_wav_bytes(), "audio/wav")},
    )
    ok = status == 401
    return ProbeResult(
        "voice_transcribe_unauth",
        "pass" if ok else "fail",
        f"POST {VOICE_TRANSCRIBE_PATH} without auth -> {status}",
    )


def probe_auth_me(host: str, token: str) -> ProbeResult:
    status, body = get_json(host, AUTH_ME_PATH, bearer=token)
    ok = status == 200 and bool(body.get("accountId"))
    return ProbeResult(
        "voice_auth_me",
        "pass" if ok else "fail",
        f"GET {AUTH_ME_PATH} -> {status} accountId={body.get('accountId', '')!r}",
    )


def probe_voice_ticket(host: str, token: str) -> ProbeResult:
    status, body = post_json(host, VOICE_TICKET_PATH, bearer=token)
    ticket = str(body.get("ticket") or "").strip()
    ok = status == 200 and bool(ticket)
    return ProbeResult(
        "voice_ticket",
        "pass" if ok else "fail",
        f"POST {VOICE_TICKET_PATH} -> {status} ticket={'yes' if ticket else 'no'}",
    )


def _transcript_ok(text: str, *, strict: bool) -> bool:
    return probe_transcript_ok(text, strict=strict)


async def _recv_ws_transcript(ws, *, timeout: float = 45) -> dict | None:
    message: dict | None = None
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            break
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        frame = json.loads(raw)
        if frame.get("type") == "error":
            return frame
        if frame.get("type") == "transcript":
            message = frame
            if frame.get("is_final"):
                break
    return message


def _evaluate_ws_message(name: str, ws_path: str, message: dict | None, *, strict: bool) -> ProbeResult:
    if message is None:
        return ProbeResult(name, "fail", f"WS {ws_path} no transcript frame received")
    if message.get("type") == "error":
        if not strict:
            return ProbeResult(name, "warn", f"WS {ws_path} -> error frame: {message.get('message', '')!r}")
        return ProbeResult(name, "fail", f"WS {ws_path} error frame: {message}")
    if message.get("type") != "transcript":
        return ProbeResult(name, "fail", f"WS {ws_path} unexpected frame: {message}")
    text = str(message.get("text") or "")
    if message.get("is_final") and _transcript_ok(text, strict=strict):
        return ProbeResult(
            name,
            "pass",
            f"WS {ws_path} -> transcript is_final={message.get('is_final')} text={text!r}",
        )
    if not strict:
        return ProbeResult(name, "warn", f"WS {ws_path} -> transcript without expected text: {text!r}")
    return ProbeResult(name, "fail", f"WS {ws_path} transcript not acceptable: {message}")


def probe_voice_transcribe_auth(host: str, token: str, *, strict: bool) -> ProbeResult:
    status, body = post_multipart(
        host,
        VOICE_TRANSCRIBE_PATH,
        files={"audio": ("clip.wav", probe_wav_bytes(), "audio/wav")},
        bearer=token,
    )
    if status == 200:
        text = str(body.get("text") or "")
        has_keys = "text" in body and "intent" in body
        ok = has_keys and _transcript_ok(text, strict=strict)
        level = "pass" if ok else ("fail" if strict else "warn")
        return ProbeResult(
            "voice_transcribe_auth",
            level,
            f"POST {VOICE_TRANSCRIBE_PATH} -> 200 text={text!r} intent={body.get('intent', {}).get('capability', '')!r}",
        )
    if status == 503:
        detail = body.get("detail") or body.get("message") or body
        level = "fail" if strict else "warn"
        return ProbeResult(
            "voice_transcribe_auth",
            level,
            f"POST {VOICE_TRANSCRIBE_PATH} -> 503 ({detail}); ASR unavailable",
        )
    return ProbeResult(
        "voice_transcribe_auth",
        "fail",
        f"POST {VOICE_TRANSCRIBE_PATH} -> {status}: {body}",
    )


async def _probe_voice_ws_path(
    host: str,
    ticket: str,
    ws_path: str,
    *,
    strict: bool,
    connect_ws: Callable | None = None,
) -> ProbeResult:
    name = f"voice_ws{ws_path.replace('/', '_')}"
    if connect_ws is None:
        try:
            import websockets
        except ImportError as exc:
            return ProbeResult(name, "fail", f"websockets not installed: {exc}")

        def _default_connect(url: str):
            return websockets.connect(url, additional_headers={"User-Agent": "LiMaVoiceE2E/1.0"})

        connect_ws = _default_connect

    from ws_ticket_http import ws_url_with_ticket

    url = ws_url_with_ticket(f"wss://{host}{ws_path}", ticket)
    try:
        async with connect_ws(url) as ws:
            for chunk in probe_pcm_chunks():
                await ws.send(chunk)
            await ws.send("stop")
            message = await _recv_ws_transcript(ws)
        return _evaluate_ws_message(name, ws_path, message, strict=strict)
    except Exception as exc:
        code = getattr(exc, "code", None)
        status_code = getattr(exc, "status_code", None) or code
        if status_code in {1013, 403}:
            level = "fail" if strict else "warn"
            return ProbeResult(
                name,
                level,
                f"WS {ws_path} rejected ({status_code}); ASR likely unavailable",
            )
        if code == 4401:
            return ProbeResult(name, "fail", f"WS {ws_path} closed 4401 (invalid ticket)")
        return ProbeResult(name, "fail", f"WS {ws_path} -> {type(exc).__name__}: {exc}")


async def probe_voice_ws_legacy(
    host: str, ticket: str, *, strict: bool, connect_ws: Callable | None = None
) -> ProbeResult:
    return await _probe_voice_ws_path(host, ticket, LEGACY_VOICE_WS_PATH, strict=strict, connect_ws=connect_ws)


async def probe_voice_ws_app(
    host: str, ticket: str, *, strict: bool, connect_ws: Callable | None = None
) -> ProbeResult:
    return await _probe_voice_ws_path(host, ticket, APP_VOICE_WS_PATH, strict=strict, connect_ws=connect_ws)


async def run_voice_e2e_probes(
    host: str,
    *,
    token: str | None = None,
    strict: bool | None = None,
    include_ws: bool = True,
    connect_ws: Callable | None = None,
) -> list[ProbeResult]:
    """Run voice probes; shallow auth checks always, WS when include_ws and ticket available."""
    if strict is None:
        strict = voice_e2e_strict()
    results = [probe_voice_transcribe_unauth(host)]
    bearer = token
    if bearer is None:
        bearer, source = resolve_device_app_token(host)
        if bearer is None:
            results.append(ProbeResult("voice_auth_e2e", "skip", source))
            return results
        results.append(ProbeResult("voice_auth_source", "pass", f"token from {source}"))

    results.append(probe_auth_me(host, bearer))
    ticket_result = probe_voice_ticket(host, bearer)
    results.append(ticket_result)
    results.append(probe_voice_transcribe_auth(host, bearer, strict=strict))

    if not include_ws or ticket_result.status != "pass":
        return results

    status, body = post_json(host, VOICE_TICKET_PATH, bearer=bearer)
    legacy_ticket = str(body.get("ticket") or "").strip()
    if not legacy_ticket:
        results.append(ProbeResult("voice_ws_legacy", "fail", "could not mint WS ticket"))
        return results

    results.append(await probe_voice_ws_legacy(host, legacy_ticket, strict=strict, connect_ws=connect_ws))

    status, body = post_json(host, VOICE_TICKET_PATH, bearer=bearer)
    app_ticket = str(body.get("ticket") or "").strip()
    if app_ticket:
        results.append(await probe_voice_ws_app(host, app_ticket, strict=strict, connect_ws=connect_ws))
    else:
        results.append(ProbeResult("voice_ws_device_v1_app_voice_ws", "fail", "could not mint app WS ticket"))
    return results


def print_probe_results(results: list[ProbeResult]) -> None:
    for item in results:
        label = item.status.upper()
        print(f"{label} {item.name} - {item.message}")


def exit_code_for_results(results: list[ProbeResult]) -> int:
    if any(item.status == "fail" for item in results):
        return 1
    return 0
