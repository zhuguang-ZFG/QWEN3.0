"""Static OpenAPI docs for voice WebSocket paths (FastAPI does not export WS)."""

from __future__ import annotations

from typing import Any

VOICE_WS_DOC: dict[str, Any] = {
    "get": {
        "tags": ["device-app-voice-ws"],
        "summary": "Realtime Voice WebSocket",
        "description": (
            "HTTP Upgrade to WebSocket for streaming ASR. "
            "Connect with `?ticket=` from POST /device/v1/app/voice/ticket. "
            "Send PCM binary frames (16 kHz mono), text `stop` to finalize, text `ping` for keepalive. "
            "Server replies with JSON `{type:transcript|pong|error}`. WS does not return intent — "
            "use REST /voice/transcribe or client-side resolve. See docs-site/api/voice.md."
        ),
        "parameters": [
            {
                "name": "ticket",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
                "example": "tk-xxxxxxxx",
                "description": "One-time ticket (TTL 30s); consumed after successful accept.",
            },
            {
                "name": "device_id",
                "in": "query",
                "required": False,
                "schema": {"type": "string"},
                "description": (
                    "Optional; when set, account must own or have control share (else close 4403, ticket kept)."
                ),
            },
        ],
        "responses": {
            "101": {"description": "Switching Protocols (WebSocket upgrade)"},
            "400": {"description": "Missing or invalid ticket"},
            "4403": {"description": "device_id present but control permission denied (close code)"},
            "4429": {"description": "Rate limited / concurrent slot full (close code)"},
        },
    }
}
