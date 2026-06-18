"""Voiceprint sample handling for device gateway WebSocket uplink."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.protocol import ack_frame, build_voiceprint_sample_ack
from device_gateway.sessions import registry
from device_intelligence.shadow import shadow_store

_log = logging.getLogger(__name__)


async def handle_voiceprint_sample(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> None:
    """Store a voiceprint sample and optionally extract its embedding."""
    validated = shadow_store.validate_voiceprint_sample(message)
    member_id = validated.get("member_id") or ""
    voiceprint_id = validated.get("voiceprint_id") or ""
    sample_index = validated.get("sample_index", 0)

    try:
        from session_memory.store_voiceprint import upsert_voiceprint_sample

        upsert_voiceprint_sample(
            voiceprint_id=voiceprint_id,
            member_id=member_id,
            device_id=device_id,
            sample_index=sample_index,
            audio_data=validated.get("audio_data") or "",
            format=validated.get("format") or "raw_pcm",
        )

        ack = build_voiceprint_sample_ack(
            device_id=device_id,
            voiceprint_id=voiceprint_id,
            sample_index=sample_index,
            request_id=request_id,
        )
        await websocket.send_json(ack)
    except ImportError:
        _log.warning("session_memory.store_db not installed; skipping voiceprint sample validation")
        await websocket.send_json(
            ack_frame(
                "voiceprint_sample_ack",
                device_id,
                voiceprint_id=voiceprint_id,
                sample_index=sample_index,
                request_id=request_id,
            )
        )
        return

    # Extract 3D-Speaker embedding (Task 8)
    from routes.device_voice_ws_helpers import _extract_and_store_voiceprint_embedding

    await _extract_and_store_voiceprint_embedding(validated, voiceprint_id, member_id, device_id)

    shadow_store.update_voiceprint_sample(message)
    session = registry.get(device_id)
    if session is not None:
        await session.send_json(
            ack_frame(
                "voiceprint_sample_ack",
                device_id,
                voiceprint_id=voiceprint_id,
                sample_index=sample_index,
                request_id=request_id,
            )
        )
