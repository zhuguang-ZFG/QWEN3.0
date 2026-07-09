"""Minimal device voice ASR facade (post-slimdown)."""

from device_voice.asr import (
    AsrNotConfiguredError,
    get_asr_provider,
    prepare_pcm,
    transcribe_audio,
    transcribe_pcm,
)
from device_voice.providers.registry import supported_asr_providers

__all__ = [
    "AsrNotConfiguredError",
    "get_asr_provider",
    "prepare_pcm",
    "supported_asr_providers",
    "transcribe_audio",
    "transcribe_pcm",
]
