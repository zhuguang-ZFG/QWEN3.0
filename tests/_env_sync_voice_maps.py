"""Voice-provider env-to-singleton mappings for the test monkeypatch wrapper."""

from __future__ import annotations

from typing import Any, Callable

from tests._env_sync_maps import _strip_or_empty


_Map = dict[str, tuple[Any, str, Callable[[str | None], Any]]]


def _voice_providers_map(settings: Any) -> _Map:
    result: _Map = {}
    result.update(_doubao_asr_map(settings))
    result.update(_aliyun_nls_map(settings))
    result.update(_dashscope_asr_map(settings))
    result.update(_whisper_map(settings))
    result.update(_dashscope_tts_map(settings))
    result.update(_doubao_tts_map(settings))
    result.update(_mimo_map(settings))
    return result


def _doubao_asr_map(settings: Any) -> _Map:
    return {
        "DOUBAO_ASR_APPID": (settings.VOICE_PROVIDERS.doubao_asr, "appid", _strip_or_empty),
        "DOUBAO_ASR_ACCESS_TOKEN": (
            settings.VOICE_PROVIDERS.doubao_asr,
            "access_token",
            _strip_or_empty,
        ),
        "DOUBAO_ASR_CLUSTER": (settings.VOICE_PROVIDERS.doubao_asr, "cluster", _strip_or_empty),
    }


def _aliyun_nls_map(settings: Any) -> _Map:
    return {
        "ALIBABA_CLOUD_ACCESS_KEY_ID": (
            settings.VOICE_PROVIDERS.aliyun_nls,
            "ak_id",
            _strip_or_empty,
        ),
        "ALIYUN_AK_ID": (settings.VOICE_PROVIDERS.aliyun_nls, "ak_id", _strip_or_empty),
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET": (
            settings.VOICE_PROVIDERS.aliyun_nls,
            "ak_secret",
            _strip_or_empty,
        ),
        "ALIYUN_AK_SECRET": (settings.VOICE_PROVIDERS.aliyun_nls, "ak_secret", _strip_or_empty),
        "ALIBABA_NLS_APP_KEY": (settings.VOICE_PROVIDERS.aliyun_nls, "app_key", _strip_or_empty),
        "ALIBABA_NLS_REGION": (settings.VOICE_PROVIDERS.aliyun_nls, "region", _strip_or_empty),
        "ALIBABA_NLS_TTS_VOICE": (
            settings.VOICE_PROVIDERS.aliyun_nls,
            "tts_voice",
            _strip_or_empty,
        ),
    }


def _dashscope_asr_map(settings: Any) -> _Map:
    return {
        "DASHSCOPE_ASR_MODEL": (settings.VOICE_PROVIDERS.dashscope_asr, "model", _strip_or_empty),
    }


def _whisper_map(settings: Any) -> _Map:
    return {
        "WHISPER_MODEL": (settings.VOICE_PROVIDERS.whisper, "model", _strip_or_empty),
        "WHISPER_DEVICE": (settings.VOICE_PROVIDERS.whisper, "device", _strip_or_empty),
        "WHISPER_COMPUTE_TYPE": (
            settings.VOICE_PROVIDERS.whisper,
            "compute_type",
            _strip_or_empty,
        ),
        "WHISPER_LANGUAGE": (settings.VOICE_PROVIDERS.whisper, "language", _strip_or_empty),
    }


def _dashscope_tts_map(settings: Any) -> _Map:
    return {
        "DASHSCOPE_TTS_MODEL": (settings.VOICE_PROVIDERS.dashscope_tts, "model", _strip_or_empty),
    }


def _doubao_tts_map(settings: Any) -> _Map:
    return {
        "DOUBAO_TTS_APPID": (settings.VOICE_PROVIDERS.doubao_tts, "appid", _strip_or_empty),
        "DOUBAO_TTS_ACCESS_TOKEN": (
            settings.VOICE_PROVIDERS.doubao_tts,
            "access_token",
            _strip_or_empty,
        ),
        "DOUBAO_TTS_CLUSTER": (settings.VOICE_PROVIDERS.doubao_tts, "cluster", _strip_or_empty),
        "DOUBAO_TTS_VOICE": (settings.VOICE_PROVIDERS.doubao_tts, "voice", _strip_or_empty),
        "DOUBAO_TTS_ENCODING": (
            settings.VOICE_PROVIDERS.doubao_tts,
            "encoding",
            _strip_or_empty,
        ),
    }


def _mimo_map(settings: Any) -> _Map:
    return {
        "MIMO_API_KEY": (settings.VOICE_PROVIDERS.mimo, "api_key", _strip_or_empty),
        "MIMO_TTS_MODEL": (settings.VOICE_PROVIDERS.mimo, "model", _strip_or_empty),
        "MIMO_TTS_VOICE": (settings.VOICE_PROVIDERS.mimo, "voice", _strip_or_empty),
        "MIMO_TTS_FORMAT": (settings.VOICE_PROVIDERS.mimo, "format", _strip_or_empty),
    }
