"""Audio/voiceprint helper functions for device gateway WebSocket handlers."""

from __future__ import annotations

import base64
import logging
import struct
from typing import Any

from fastapi import WebSocket

from device_intelligence.shadow import shadow_store
from device_gateway.protocol import voice_status_frame, audio_reply_frame

_log = logging.getLogger(__name__)

# In-memory audio buffer registry: device_id -> (VADState, vad_provider)
_audio_registry: dict[str, tuple] = {}


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
    try:
        pcm_bytes = base64.b64decode(data_b64)
    except Exception:
        _log.debug("device=%s invalid base64 audio data", device_id)
        return True

    is_end = message.get("is_end", False)
    await _feed_audio_to_pipeline(websocket, device_id, pcm_bytes, is_end)
    return True


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

    try:
        from device_voice.vad import VADModelUnavailableError, VADState
    except ImportError:
        _log.debug("device_voice.vad not available")
        return

    if device_id not in _audio_registry:
        from device_voice import get_vad_provider

        vad = get_vad_provider()
        _audio_registry[device_id] = (VADState(), vad)

    vad_state, vad_provider = _audio_registry[device_id]

    # Feed chunk through VAD
    try:
        vad_provider.detect(pcm_chunk, vad_state)
    except VADModelUnavailableError:
        _log.warning("device=%s VAD model unavailable; dropping audio chunk", device_id)
        await websocket.send_json(voice_status_frame(device_id, "error", error="vad_model_unavailable"))
        return

    # Check for utterance end
    utterance_ended = is_end or vad_provider.is_utterance_end(vad_state)

    if utterance_ended and len(vad_state.speech_buffer) > 0:
        pcm_data = bytes(vad_state.speech_buffer)
        vad_provider.reset(vad_state)

        # Send listening->transcribing status
        await websocket.send_json(voice_status_frame(device_id, "transcribing"))

        # Run dialogue pipeline
        try:
            from device_voice.dialogue import process_voice_utterance

            result = await process_voice_utterance(pcm_data, device_id)
        except Exception:
            _log.warning("device=%s dialogue pipeline failed", device_id, exc_info=True)
            await websocket.send_json(voice_status_frame(device_id, "idle"))
            return

        transcript = result.get("transcript", "")
        reply_audio = result.get("reply_audio", b"")

        # Send transcript status
        if transcript:
            await websocket.send_json(voice_status_frame(device_id, "speaking", transcript=transcript))

        # Update shadow with voiceprint result
        voiceprint_result = result.get("voiceprint")
        if voiceprint_result:
            shadow_store.update_voiceprint_result(device_id, voiceprint_result)

        # Send audio reply: metadata (JSON) then binary PCM
        if reply_audio:
            await websocket.send_json(audio_reply_frame(device_id))
            await websocket.send_bytes(reply_audio)

        # Return to idle
        await websocket.send_json(voice_status_frame(device_id, "idle"))


def _cleanup_audio_registry(device_id: str) -> None:
    """Remove audio pipeline state for a disconnected device."""
    _audio_registry.pop(device_id, None)


async def _extract_and_store_voiceprint_embedding(
    validated: dict[str, Any],
    voiceprint_id: str,
    member_id: str,
    device_id: str,
) -> None:
    """Extract 3D-Speaker embedding from voiceprint sample and store in DB."""
    audio_data_b64 = validated.get("audio_data", "")
    fmt = validated.get("format", "raw_pcm")

    try:
        audio_bytes = base64.b64decode(audio_data_b64)
    except Exception:
        _log.debug("device=%s voiceprint_id=%s failed to decode audio", device_id, voiceprint_id)
        return

    if not audio_bytes:
        return

    try:
        from device_voice import VOICE_ENABLED

        if not VOICE_ENABLED:
            _log.debug("device_voice not enabled; skipping voiceprint embedding extraction")
            return

        from device_voice.voiceprint import get_voiceprint_provider

        provider = get_voiceprint_provider()
        if not provider.enabled:
            return

        # Convert audio to WAV if needed
        wav_bytes = _ensure_wav(audio_bytes, fmt)
        if wav_bytes is None:
            _log.debug("device=%s voiceprint_id=%s failed to convert audio format", device_id, voiceprint_id)
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
            _log.debug("session_memory.store_db not available for embedding storage")
    except Exception:
        _log.warning("device=%s voiceprint embedding extraction failed", device_id, exc_info=True)


def _ensure_wav(audio_bytes: bytes, fmt: str) -> bytes | None:
    """Convert raw PCM audio bytes to WAV format if needed."""
    if fmt in ("wav",):
        return audio_bytes

    if fmt in ("raw_pcm", "pcm"):
        # Add WAV header to raw PCM (16kHz, 16-bit, mono)
        return _pcm_to_wav(audio_bytes, sample_rate=16000, channels=1, bits_per_sample=16)

    _log.debug("Unsupported voiceprint audio format: %s", fmt)
    return None


def _pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int = 16000,
    channels: int = 1,
    bits_per_sample: int = 16,
) -> bytes:
    """Add a WAV header to raw PCM bytes."""
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_data)

    wav_header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,  # Subchunk1Size (PCM)
        1,  # AudioFormat (PCM = 1)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return wav_header + pcm_data


__all__ = [
    "_audio_registry",
    "handle_audio_chunk",
    "_feed_audio_to_pipeline",
    "_cleanup_audio_registry",
    "_extract_and_store_voiceprint_embedding",
    "_ensure_wav",
    "_pcm_to_wav",
]
