"""Voice dialogue pipeline — ASR → LLM → TTS.

Integrates the voice providers with LiMa's existing routing engine and
session memory to deliver a complete voice conversation loop.

Flow:
    audio PCM → [voiceprint identify] → VAD detect → ASR transcribe
    → routing_engine.route() → LLM reply text → TTS synthesize → audio PCM reply
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from device_voice.audio_stream import AudioConfig, estimate_duration_ms

_log = logging.getLogger(__name__)


async def process_voice_utterance(
    pcm_data: bytes,
    device_id: str,
    *,
    audio_config: AudioConfig | None = None,
    voice: str = "",
) -> dict[str, Any]:
    """Process a complete voice utterance through the dialogue pipeline.

    Args:
        pcm_data: Raw PCM bytes for the utterance (VAD has already isolated it).
        device_id: Device identifier for routing and memory context.
        audio_config: Audio format config (default 16kHz 16-bit mono).
        voice: TTS voice preference (empty = provider default).

    Returns:
        Dict with keys: transcript, reply_text, reply_audio (PCM bytes),
        asr_ms, llm_ms, tts_ms, total_ms, voiceprint.
    """
    cfg = audio_config or AudioConfig()
    t0 = time.monotonic()

    # ── Voiceprint Identification (Task 8) ──
    voiceprint_result: Optional[dict[str, Any]] = None
    try:
        voiceprint_result = await _identify_speaker(pcm_data, device_id, cfg)
    except Exception:
        _log.debug("device=%s voiceprint identification skipped", device_id, exc_info=True)

    # ── ASR ──
    asr_start = time.monotonic()
    transcript = await _run_asr(pcm_data, cfg)
    asr_ms = (time.monotonic() - asr_start) * 1000

    if not transcript or not transcript.strip():
        _log.debug("device=%s ASR returned empty transcript", device_id)
        return _empty_result(pcm_data, asr_ms, 0, 0, t0, voiceprint_result)

    _log.info(
        "device=%s ASR: '%s' (%.0fms, audio %.0fms)",
        device_id,
        transcript[:80],
        asr_ms,
        estimate_duration_ms(len(pcm_data), cfg),
    )

    # ── LLM via LiMa routing engine ──
    llm_start = time.monotonic()
    reply_text = await _run_llm(transcript, device_id)
    llm_ms = (time.monotonic() - llm_start) * 1000

    if not reply_text:
        _log.debug("device=%s LLM returned empty reply", device_id)
        return _empty_result(pcm_data, asr_ms, llm_ms, 0, t0, voiceprint_result)

    # ── TTS ──
    tts_start = time.monotonic()
    reply_audio = await _run_tts(reply_text, voice, cfg)
    tts_ms = (time.monotonic() - tts_start) * 1000

    total_ms = (time.monotonic() - t0) * 1000
    _log.info(
        "device=%s dialogue complete: ASR %.0fms | LLM %.0fms | TTS %.0fms | total %.0fms",
        device_id,
        asr_ms,
        llm_ms,
        tts_ms,
        total_ms,
    )

    return {
        "transcript": transcript,
        "reply_text": reply_text,
        "reply_audio": reply_audio,
        "asr_ms": asr_ms,
        "llm_ms": llm_ms,
        "tts_ms": tts_ms,
        "total_ms": total_ms,
        "voiceprint": voiceprint_result,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _identify_speaker(
    pcm_data: bytes, device_id: str, config: AudioConfig
) -> dict[str, Any] | None:
    """Run voiceprint identification on the utterance audio.

    Returns a dict with speaker identity info, or None if identification
    was skipped or failed.
    """
    try:
        from device_voice.voiceprint import get_voiceprint_provider
        provider = get_voiceprint_provider()
        if not provider.enabled:
            return None

        # Convert PCM to WAV for the model
        wav_data = _pcm_to_wav(pcm_data, config.sample_rate)
        result = await provider.identify_speaker(wav_data, device_id)

        return {
            "is_known": result.is_known,
            "member_id": result.member_id,
            "display_name": result.display_name,
            "confidence": result.confidence,
            "speaker_ref": result.speaker_ref,
        }
    except ImportError:
        _log.debug("device_voice.voiceprint not available")
        return None
    except Exception:
        _log.warning("device=%s voiceprint identification failed", device_id, exc_info=True)
        return None


async def _run_asr(pcm_data: bytes, config: AudioConfig) -> str:
    """Run ASR provider on PCM data."""
    try:
        from device_voice import get_asr_provider
        asr = get_asr_provider()
        return await asr.transcribe(pcm_data, sample_rate=config.sample_rate)
    except Exception:
        _log.warning("ASR provider failed", exc_info=True)
        return ""


async def _run_llm(transcript: str, device_id: str) -> str:
    """Send transcript through LiMa's routing engine and return reply text.

    This bridges the voice pipeline into LiMa's existing 170+ backend routing.
    The routing_engine handles model selection, health scoring, budget, and
    fallback — the voice pipeline just needs the final reply text.
    """
    try:
        import asyncio
        from routing_engine import route
        result = await asyncio.to_thread(
            route,
            query=transcript,
            messages=[{"role": "user", "content": transcript}],
            ide_source="voice",
        )
        # route() returns a dict or response object; extract text content
        if isinstance(result, dict):
            return result.get("reply", result.get("text", ""))
        if isinstance(result, str):
            return result
        # FastAPI Response objects — extract body
        if hasattr(result, "body"):
            import json
            body = json.loads(result.body)
            choices = body.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
        return ""
    except Exception:
        _log.warning("LLM routing failed for device=%s", device_id, exc_info=True)
        return ""


async def _run_tts(text: str, voice: str, config: AudioConfig) -> bytes:
    """Run TTS provider to synthesize reply audio."""
    try:
        from device_voice import get_tts_provider
        tts = get_tts_provider()
        return await tts.synthesize(text, voice=voice, sample_rate=config.sample_rate)
    except Exception:
        _log.warning("TTS provider failed", exc_info=True)
        return b""


def _empty_result(
    pcm_data: bytes,
    asr_ms: float,
    llm_ms: float,
    tts_ms: float,
    t0: float,
    voiceprint_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total_ms = (time.monotonic() - t0) * 1000
    result = {
        "transcript": "",
        "reply_text": "",
        "reply_audio": b"",
        "asr_ms": asr_ms,
        "llm_ms": llm_ms,
        "tts_ms": tts_ms,
        "total_ms": total_ms,
    }
    if voiceprint_result is not None:
        result["voiceprint"] = voiceprint_result
    return result


def _pcm_to_wav(
    pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bits_per_sample: int = 16
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
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return wav_header + pcm_data
