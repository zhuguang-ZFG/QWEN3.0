"""Audio/voiceprint helper functions for device gateway WebSocket handlers."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

from fastapi import WebSocket

from device_intelligence.shadow import shadow_store
from device_voice.audio_stream import AudioConfig, pcm_to_wav
from device_gateway.protocol import voice_status_frame, audio_reply_frame

_log = logging.getLogger(__name__)

# In-memory audio buffer registry: device_id -> (VADState, vad_provider)
_audio_registry: dict[str, tuple] = {}

# Max decoded PCM bytes per audio chunk / voiceprint sample (default 1 MiB).
_MAX_AUDIO_BYTES = int(os.environ.get("LIMA_VOICE_MAX_AUDIO_BYTES", "1048576"))


def _decode_limited_audio(data_b64: str, device_id: str, label: str) -> bytes | None:
    """Decode base64 audio and enforce a size ceiling."""
    try:
        pcm_bytes = base64.b64decode(data_b64)
    except Exception:
        _log.warning("device=%s invalid base64 %s data", device_id, label)
        return None
    if len(pcm_bytes) > _MAX_AUDIO_BYTES:
        _log.warning(
            "device=%s %s data exceeds limit: %d > %d bytes",
            device_id,
            label,
            len(pcm_bytes),
            _MAX_AUDIO_BYTES,
        )
        return None
    return pcm_bytes


async def handle_audio_chunk(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> bool:
    """Handle JSON-encoded audio chunk (base64 PCM).

    Decodes base64 data and feeds it into the per-connection audio pipeline.
    Returns True to keep the connection open.
    """
    data_b64 = message.get("data", "")
    pcm_bytes = _decode_limited_audio(data_b64, device_id, "audio")
    if pcm_bytes is None:
        return True

    is_end = message.get("is_end", False)
    await _feed_audio_to_pipeline(websocket, device_id, pcm_bytes, is_end)
    return True


def _get_vad_state(device_id: str) -> tuple[Any, Any] | None:
    """Return (vad_state, vad_provider) for *device_id*, initializing if needed."""
    try:
        from device_voice.vad import VADState
    except ImportError:
        _log.warning("device_voice.vad not available")
        return None

    if device_id not in _audio_registry:
        from device_voice import get_vad_provider

        vad = get_vad_provider()
        _audio_registry[device_id] = (VADState(), vad)

    return _audio_registry[device_id]


async def _detect_utterance(
    websocket: WebSocket,
    device_id: str,
    pcm_chunk: bytes,
    vad_state: Any,
    vad_provider: Any,
) -> bool:
    """Feed chunk to VAD and return True if an utterance has ended."""
    from device_voice.vad import VADModelUnavailableError

    try:
        vad_provider.detect(pcm_chunk, vad_state)
    except VADModelUnavailableError:
        _log.warning("device=%s VAD model unavailable; dropping audio chunk", device_id)
        await websocket.send_json(voice_status_frame(device_id, "error", error="vad_model_unavailable"))
        return False

    return len(vad_state.speech_buffer) > 0


async def _process_utterance(
    websocket: WebSocket,
    device_id: str,
    pcm_data: bytes,
) -> None:
    """Run dialogue pipeline for a completed utterance and send replies."""
    await websocket.send_json(voice_status_frame(device_id, "transcribing"))

    try:
        from device_voice.dialogue import process_voice_utterance

        client_ip = _client_ip_from_websocket(websocket)
        result = await process_voice_utterance(pcm_data, device_id, client_ip=client_ip)
    except Exception:
        _log.warning("device=%s dialogue pipeline failed", device_id, exc_info=True)
        await websocket.send_json(voice_status_frame(device_id, "idle"))
        return

    transcript = result.get("transcript", "")
    reply_audio = result.get("reply_audio", b"")

    if transcript:
        await websocket.send_json(voice_status_frame(device_id, "speaking", transcript=transcript))

    voiceprint_result = result.get("voiceprint")
    if voiceprint_result:
        shadow_store.update_voiceprint_result(device_id, voiceprint_result)

    if reply_audio:
        await websocket.send_json(audio_reply_frame(device_id))
        await websocket.send_bytes(reply_audio)

    await websocket.send_json(voice_status_frame(device_id, "idle"))


async def _feed_audio_to_pipeline(
    websocket: WebSocket,
    device_id: str,
    pcm_chunk: bytes,
    is_end: bool = False,
) -> None:
    """Feed a PCM audio chunk through VAD -> dialogue -> TTS reply."""
    from device_voice import VOICE_ENABLED

    if not VOICE_ENABLED:
        return

    state_pair = _get_vad_state(device_id)
    if state_pair is None:
        return
    vad_state, vad_provider = state_pair

    if not await _detect_utterance(websocket, device_id, pcm_chunk, vad_state, vad_provider):
        return

    utterance_ended = is_end or vad_provider.is_utterance_end(vad_state)
    if not utterance_ended:
        return

    pcm_data = bytes(vad_state.speech_buffer)
    vad_provider.reset(vad_state)
    await _process_utterance(websocket, device_id, pcm_data)


def _cleanup_audio_registry(device_id: str) -> None:
    """Remove audio pipeline state for a disconnected device."""
    _audio_registry.pop(device_id, None)


def _client_ip_from_websocket(websocket: WebSocket) -> str:
    """Best-effort client IP extraction from WS scope/headers."""
    scope = websocket.scope
    client = scope.get("client")
    if isinstance(client, (list, tuple)) and len(client) >= 1:
        return str(client[0])
    forwarded = websocket.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return websocket.headers.get("x-real-ip", "127.0.0.1")


async def _extract_and_store_voiceprint_embedding(
    validated: dict[str, Any],
    voiceprint_id: str,
    member_id: str,
    device_id: str,
) -> None:
    """Extract 3D-Speaker embedding from voiceprint sample and store in DB."""
    audio_data_b64 = validated.get("audio_data", "")
    fmt = validated.get("format", "raw_pcm")

    audio_bytes = _decode_limited_audio(audio_data_b64, device_id, "voiceprint")
    if not audio_bytes:
        return

    try:
        from device_voice import VOICE_ENABLED

        if not VOICE_ENABLED:
            _log.warning("device_voice not enabled; skipping voiceprint embedding extraction")
            return

        from device_voice.voiceprint import get_voiceprint_provider

        provider = get_voiceprint_provider()
        if not provider.enabled:
            return

        # Convert audio to WAV if needed
        wav_bytes = _ensure_wav(audio_bytes, fmt)
        if wav_bytes is None:
            _log.warning("device=%s voiceprint_id=%s failed to convert audio format", device_id, voiceprint_id)
            return

        embedding = await provider.register_speaker(wav_bytes, member_id, device_id)
        if embedding is None:
            return

        # Store the embedding vector in the database
        try:
            from session_memory.store_voiceprint import store_voiceprint_embedding

            store_voiceprint_embedding(
                voiceprint_id=voiceprint_id,
                member_id=member_id,
                device_id=device_id,
                embedding=embedding,
            )
            _log.info("device=%s voiceprint_id=%s embedding stored dim=%d", device_id, voiceprint_id, len(embedding))

            # Invalidate cache so next identify_speaker picks up the new embedding
            await provider.invalidate_cache(device_id)
        except ImportError:
            _log.warning("session_memory.store_db not available for embedding storage")
    except Exception:
        _log.warning("device=%s voiceprint embedding extraction failed", device_id, exc_info=True)


def _ensure_wav(audio_bytes: bytes, fmt: str, config: AudioConfig | None = None) -> bytes | None:
    """Convert raw PCM audio bytes to WAV format if needed."""
    if fmt in ("wav",):
        return audio_bytes

    if fmt in ("raw_pcm", "pcm"):
        cfg = config or AudioConfig()
        return pcm_to_wav(audio_bytes, cfg)

    _log.debug("Unsupported voiceprint audio format: %s", fmt)
    return None


__all__ = [
    "_audio_registry",
    "handle_audio_chunk",
    "_feed_audio_to_pipeline",
    "_cleanup_audio_registry",
    "_client_ip_from_websocket",
    "_extract_and_store_voiceprint_embedding",
    "_ensure_wav",
]
