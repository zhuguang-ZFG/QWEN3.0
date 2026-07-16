"""ASR facade for device-app voice transcribe."""

from __future__ import annotations

import asyncio

from config.voice_settings import VOICE
from device_voice.audio_format import prepare_pcm
from device_voice.providers.base import AsrNotConfiguredError, AsrProvider
from device_voice.providers.registry import create_asr_provider, normalize_asr_provider_name

__all__ = [
    "AsrNotConfiguredError",
    "AsrProvider",
    "get_asr_provider",
    "prepare_pcm",
    "transcribe_audio",
    "transcribe_pcm",
]


def content_type_for_audio(audio_data: bytes) -> str:
    from device_voice.audio_format import content_type_for_audio as _content_type

    return _content_type(audio_data)


def get_asr_provider() -> AsrProvider:
    if not VOICE.enabled:
        raise AsrNotConfiguredError("LIMA_VOICE_ENABLED is not set")
    return create_asr_provider(normalize_asr_provider_name(VOICE.asr_provider))


async def transcribe_audio(audio_data: bytes) -> str:
    provider = get_asr_provider()
    return await asyncio.wait_for(provider.transcribe(audio_data), timeout=VOICE.asr_timeout_seconds)


async def transcribe_pcm(pcm_data: bytes, *, sample_rate: int = 16000) -> str:
    from device_voice.audio_format import pcm_to_wav_bytes

    return await transcribe_audio(pcm_to_wav_bytes(pcm_data, sample_rate=sample_rate))
