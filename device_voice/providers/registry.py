"""ASR provider registry and factory."""

from __future__ import annotations

import logging

from config.backend_config import ALIYUN_API_KEY
from config.voice_settings import VOICE, VOICE_PROVIDERS
from device_voice.providers.base import AsrNotConfiguredError, AsrProvider
from device_voice.providers.dashscope import (
    DashScopeRecognitionProvider,
    Qwen3AsrFlashProvider,
    uses_streaming_model,
)
from device_voice.providers.funasr_local import FunAsrLocalProvider
from device_voice.providers.whisper_local import WhisperLocalProvider, whisper_config_or_default

_log = logging.getLogger(__name__)
_SUPPORTED = frozenset({"dashscope", "funasr", "whisper"})
_LEGACY_ALIASES = {
    "aliyun": "dashscope",
    "aliyun_fallback": "dashscope",
    "aliyun_nls": "dashscope",
    "funasr_local": "funasr",
}


def normalize_asr_provider_name(provider_name: str) -> str:
    normalized = (provider_name or "dashscope").strip().lower()
    mapped = _LEGACY_ALIASES.get(normalized, normalized)
    if mapped != normalized:
        _log.warning("legacy ASR provider %r mapped to %r", normalized, mapped)
    return mapped


def supported_asr_providers() -> tuple[str, ...]:
    """Return configured ASR provider names."""
    return tuple(sorted(_SUPPORTED))


def _dashscope_api_key() -> str:
    return VOICE_PROVIDERS.dashscope_asr.api_key or ALIYUN_API_KEY


def _create_dashscope_provider() -> AsrProvider:
    api_key = _dashscope_api_key()
    if not api_key:
        raise AsrNotConfiguredError("DashScope ASR API key is not configured")
    model = (VOICE_PROVIDERS.dashscope_asr.model or "qwen3-asr-flash").strip()
    if uses_streaming_model(model):
        return DashScopeRecognitionProvider(api_key=api_key, model=model)
    return Qwen3AsrFlashProvider(api_key=api_key, model=model)


def _create_funasr_provider() -> AsrProvider:
    return FunAsrLocalProvider(model_dir=VOICE.model_dir, language=VOICE.funasr_language)


def _create_whisper_provider() -> AsrProvider:
    model, device, compute_type, language = whisper_config_or_default()
    return WhisperLocalProvider(
        model=model,
        device=device,
        compute_type=compute_type,
        language=language or "",
    )


def create_asr_provider(provider_name: str) -> AsrProvider:
    """Instantiate an ASR provider by configured name."""
    normalized = normalize_asr_provider_name(provider_name)
    if normalized not in _SUPPORTED:
        raise AsrNotConfiguredError(f"unsupported ASR provider: {normalized}")
    if normalized == "funasr":
        return _create_funasr_provider()
    if normalized == "whisper":
        return _create_whisper_provider()
    return _create_dashscope_provider()
