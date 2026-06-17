"""Per-message handlers for device gateway WebSocket uplink (CQ-099)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.protocol import ProtocolError, ack_frame, build_voiceprint_sample_ack, hello_ack
from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import (
    ack_processing_task,
    active_tasks_for_device,
    create_task_from_transcript,
    enqueue_pending_task,
    execute_recovery,
    mark_task_dispatched,
    record_motion_event,
    remove_pending_task,
)
from device_intelligence.shadow import shadow_store
from device_ledger.events import new_event
from device_ledger.store import ledger_store
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState, WorkflowTransitionError
from routes.device_gateway_dispatch import (
    dispatch_task_to_session,
    drain_pending_tasks,
    extract_ws_token,
    record_motion_event_observability,
    send_ws_error,
)
from routes.ws_lifecycle_helpers import reattach_tasks
from routes.ws_task_helpers import record_outcome_ledger, send_recovery_ack
from device_gateway.auth import validate_device_token

_log = logging.getLogger(__name__)


async def handle_hello(
    websocket: WebSocket,
    message: dict[str, Any],
    *,
    request_id: str | None,
) -> tuple[str | None, DeviceSession | None, bool]:
    device_id = message["device_id"]
    if not validate_device_token(device_id, extract_ws_token(websocket)):
        await send_ws_error(
            websocket,
            ProtocolError("E_UNAUTHORIZED_DEVICE", "device token is invalid", request_id),
        )
        await websocket.close(code=1008)
        return None, None, False

    session = DeviceSession(
        device_id=device_id,
        websocket=websocket,
        fw_rev=message.get("fw_rev", ""),
        capabilities=message.get("capabilities", []),
    )
    previous = registry.register(session)
    if previous and previous.websocket is not websocket:
        reattach_tasks(session, previous.take_outstanding_tasks())
        try:
            await previous.websocket.close(code=1012)
        except Exception as exc:
            _log.debug("close superseded websocket device=%s: %s", device_id, type(exc).__name__)
    reattach_tasks(session, active_tasks_for_device(device_id))
    shadow_store.update_hello(message)
    await session.send_json(hello_ack(device_id, shadow_store.delta_for_hello(device_id)))
    if not await drain_pending_tasks(session):
        return device_id, session, False
    return device_id, session, True


async def handle_heartbeat(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> None:
    registry.update_heartbeat(device_id, message["uptime_ms"])
    shadow_store.update_heartbeat(device_id, message["uptime_ms"])
    session = registry.get(device_id)
    sender = session.send_json if session is not None else websocket.send_json
    await sender(
        ack_frame(
            "heartbeat_ack",
            device_id,
            uptime_ms=message["uptime_ms"],
            request_id=request_id,
        )
    )


async def handle_transcript(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> bool:
    task = create_task_from_transcript(device_id, message["text"], request_id=request_id)
    if task.get("error"):
        await websocket.send_json(
            ack_frame(
                "motion_task_failed",
                device_id,
                task_id=task["task_id"],
                error=task["error"],
                request_id=request_id,
            )
        )
        return True
    session = registry.get(device_id)
    if session is not None:
        return await dispatch_task_to_session(session, task)
    enqueue_pending_task(device_id, task)
    return False


async def handle_motion_event(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
    summary = record_motion_event(message)
    shadow_store.update_motion_event(message)
    ack_processing_task(device_id, message["task_id"])
    record_motion_event_observability(message, device_id)

    # M5: execute recovery action on failure
    recovery_result = execute_recovery(message.get("task_id", ""), device_id, message)
    if recovery_result:
        _log.info(
            "device recovery action=%s attempt=%s device_id=%s task_id=%s",
            recovery_result["action"],
            recovery_result.get("attempt", 0),
            device_id,
            message.get("task_id", ""),
        )
        session = registry.get(device_id)
        if session is not None:
            await send_recovery_ack(session, device_id, message, request_id, recovery_result)

    session = registry.get(device_id)
    if session is not None:
        session.mark_task_acknowledged(message["task_id"])
        await session.send_json(ack_frame("motion_event_ack", device_id, **summary, request_id=request_id))

    phase = message.get("phase", "")
    if phase in ("accepted", "running", "done", "failed"):
        _log.info(
            "device task phase device_id=%s task_id=%s phase=%s",
            device_id,
            message.get("task_id", ""),
            phase,
        )

    # Record to Outcome Ledger (terminal phases only)
    if phase in ("done", "failed", "cancelled"):
        record_outcome_ledger(device_id, message, phase)


async def handle_device_info(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
    shadow_store.update_device_info(message)
    session = registry.get(device_id)
    if session is not None:
        await session.send_json(ack_frame("device_info_ack", device_id, request_id=request_id))


async def handle_self_check(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
    shadow_store.update_self_check(message)
    session = registry.get(device_id)
    if session is not None:
        await session.send_json(
            ack_frame(
                "self_check_ack",
                device_id,
                status=message.get("status", "unknown"),
                request_id=request_id,
            )
        )


async def handle_voiceprint_sample(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> None:
    validated = shadow_store.validate_voiceprint_sample(message)
    member_id = validated.get("member_id")
    voiceprint_id = validated.get("voiceprint_id")
    sample_index = validated.get("sample_index", 0)

    try:
        from session_memory.store_db import upsert_voiceprint_sample

        upsert_voiceprint_sample(
            voiceprint_id=voiceprint_id,
            member_id=member_id,
            device_id=device_id,
            sample_index=sample_index,
            audio_data=validated.get("audio_data"),
            format=validated.get("format", "raw_pcm"),
        )

        ack = build_voiceprint_sample_ack(
            device_id=device_id,
            voiceprint_id=voiceprint_id,
            sample_index=sample_index,
            request_id=request_id,
        )
        await websocket.send_json(ack)
    except ImportError:
        _log.debug("session_memory.store_db not installed; skipping voiceprint sample validation")
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

    # ── Extract 3D-Speaker embedding (Task 8) ──
    await _extract_and_store_voiceprint_embedding(
        validated, voiceprint_id, member_id, device_id
    )

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


# ---------------------------------------------------------------------------
# Audio pipeline handlers (Task 5)
# ---------------------------------------------------------------------------

# In-memory audio buffer registry: device_id → (VADState, vad_provider)
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
    import base64

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
    """Feed a PCM audio chunk through VAD → dialogue → TTS reply.

    Accumulates speech in a per-device VAD state. When utterance end is
    detected (silence threshold or explicit is_end), triggers the full
    ASR→LLM→TTS pipeline and sends the audio reply.
    """
    from device_voice import VOICE_ENABLED
    if not VOICE_ENABLED:
        return

    try:
        from device_voice.vad import VADState
    except ImportError:
        _log.debug("device_voice.vad not available")
        return

    if device_id not in _audio_registry:
        from device_voice import get_vad_provider
        vad = get_vad_provider()
        _audio_registry[device_id] = (VADState(), vad)

    vad_state, vad_provider = _audio_registry[device_id]

    # Feed chunk through VAD
    vad_provider.detect(pcm_chunk, vad_state)

    # Check for utterance end
    utterance_ended = is_end or vad_provider.is_utterance_end(vad_state)

    if utterance_ended and len(vad_state.speech_buffer) > 0:
        pcm_data = bytes(vad_state.speech_buffer)
        vad_provider.reset(vad_state)

        # Send listening→transcribing status
        from device_gateway.protocol import voice_status_frame
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
            await websocket.send_json(
                voice_status_frame(device_id, "speaking", transcript=transcript)
            )

        # Update shadow with voiceprint result
        voiceprint_result = result.get("voiceprint")
        if voiceprint_result:
            shadow_store.update_voiceprint_result(device_id, voiceprint_result)

        # Send audio reply: metadata (JSON) then binary PCM
        if reply_audio:
            from device_gateway.protocol import audio_reply_frame
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
    """Extract 3D-Speaker embedding from voiceprint sample and store in DB.

    This runs after the sample is stored via upsert_voiceprint_sample.
    The embedding vector enables fast cosine-similarity speaker matching.
    """
    import base64

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
            from session_memory.store_db import store_voiceprint_embedding
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
    """Convert raw PCM audio bytes to WAV format if needed.

    Returns WAV bytes, or None if conversion fails.
    """
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
    import struct

    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_data)

    wav_header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,                 # Subchunk1Size (PCM)
        1,                  # AudioFormat (PCM = 1)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return wav_header + pcm_data
