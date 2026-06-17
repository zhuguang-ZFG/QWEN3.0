"""Server-side WebSocket proxy for Google Gemini Live.

Browsers connect to LiMa's ``/v1/live`` endpoint; LiMa forwards the
bidirectional JSON stream to ``wss://generativelanguage.googleapis.com``
using the configured ``GOOGLE_AI_KEY``. This keeps the provider key on the
server and lets the call work through LiMa's domain and any configured proxy.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import websockets
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from access_guard import configured_api_keys, constant_time_equals, extract_bearer_token

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")

_GEMINI_LIVE_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)


def _google_api_key() -> str | None:
    key = os.environ.get("GOOGLE_AI_KEY", "").strip()
    return key or None


def _validate_lima_token(token: str) -> bool:
    keys = configured_api_keys()
    if not keys or not token:
        return False
    return any(constant_time_equals(token, k) for k in keys)


@router.websocket("/live")
async def gemini_live_proxy(
    websocket: WebSocket,
    authorization: str = Query(default=""),
) -> None:
    """Relay a browser WebSocket to the Gemini Live service."""
    google_key = _google_api_key()
    if not google_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini Live is not configured on this server.",
        )

    token = extract_bearer_token(websocket.headers.get("authorization", "")) or extract_bearer_token(authorization)
    if not _validate_lima_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    await websocket.accept()

    gemini_url = f"{_GEMINI_LIVE_URL}?key={google_key}"
    try:
        async with websockets.connect(gemini_url) as gemini_ws:
            await asyncio.gather(
                _browser_to_gemini(websocket, gemini_ws),
                _gemini_to_browser(gemini_ws, websocket),
                return_exceptions=True,
            )
    except websockets.exceptions.InvalidStatusCode as exc:
        _log.warning("Gemini Live rejected connection: %s", exc)
        await websocket.close(code=1011, reason="Upstream rejected connection")
    except websockets.exceptions.WebSocketException as exc:
        _log.warning("Gemini Live WebSocket error: %s", exc)
        await websocket.close(code=1011, reason="Upstream error")
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - defensive
        _log.exception("Unexpected error in Gemini Live proxy: %s", exc)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass


async def _browser_to_gemini(browser: WebSocket, gemini: websockets.WebSocketClientProtocol) -> None:
    while True:
        try:
            message = await browser.receive()
        except WebSocketDisconnect:
            await gemini.close()
            return

        if isinstance(message, str):
            await gemini.send(message)
        elif isinstance(message, bytes):
            await gemini.send(message)
        elif isinstance(message, dict) and message.get("type") == "websocket.disconnect":
            await gemini.close()
            return


async def _gemini_to_browser(gemini: websockets.WebSocketClientProtocol, browser: WebSocket) -> None:
    try:
        async for message in gemini:
            if isinstance(message, str):
                await browser.send_text(message)
            else:
                await browser.send_bytes(message)
    except websockets.exceptions.ConnectionClosed:
        try:
            await browser.close()
        except Exception:
            pass
