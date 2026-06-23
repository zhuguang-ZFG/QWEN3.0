"""Voice-related settings (P1-2 centralized configuration).

ASR/TTS/VAD provider credentials and voiceprint configuration are grouped here
to keep config/settings.py under the file-size limit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_with_aliases(*aliases: str) -> str:
    """Return the first non-empty environment variable value."""
    for name in aliases:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


_DASHSCOPE_API_KEY = _env_with_aliases("DASHSCOPE_API_KEY", "ALIYUN_API_KEY")


@dataclass
class VoiceConfig:
    enabled: bool = os.environ.get("LIMA_VOICE_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
    asr_provider: str = os.environ.get("LIMA_VOICE_ASR_PROVIDER", "funasr").strip().lower()
    tts_provider: str = os.environ.get("LIMA_VOICE_TTS_PROVIDER", "edge").strip().lower()
    vad_provider: str = os.environ.get("LIMA_VOICE_VAD_PROVIDER", "silero").strip().lower()
    model_dir: str = os.environ.get("LIMA_VOICE_MODEL_DIR", "data/voice_models")
    max_audio_bytes: int = int(os.environ.get("LIMA_VOICE_MAX_AUDIO_BYTES", "1048576"))


def _parse_voiceprint_threshold() -> float:
    raw = os.environ.get("LIMA_VOICEPRINT_SIMILARITY_THRESHOLD", "0.6")
    try:
        return float(raw)
    except (ValueError, TypeError):
        return 0.6


@dataclass
class VoiceprintConfig:
    mode: str = os.environ.get("LIMA_VOICEPRINT_MODE", "local").strip().lower()
    api_url: str = os.environ.get("LIMA_VOICEPRINT_API_URL", "").strip()
    api_key: str = os.environ.get("LIMA_VOICEPRINT_API_KEY", "").strip()
    similarity_threshold: float = field(default_factory=_parse_voiceprint_threshold)


@dataclass
class DoubaoASRConfig:
    appid: str = os.environ.get("DOUBAO_ASR_APPID", "").strip()
    access_token: str = os.environ.get("DOUBAO_ASR_ACCESS_TOKEN", "").strip()
    cluster: str = os.environ.get("DOUBAO_ASR_CLUSTER", "").strip()


@dataclass
class AliyunNLSConfig:
    ak_id: str = _env_with_aliases("ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIYUN_AK_ID")
    ak_secret: str = _env_with_aliases("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "ALIYUN_AK_SECRET")
    app_key: str = os.environ.get("ALIBABA_NLS_APP_KEY", "").strip()
    region: str = os.environ.get("ALIBABA_NLS_REGION", "").strip()
    tts_voice: str = os.environ.get("ALIBABA_NLS_TTS_VOICE", "").strip()


@dataclass
class DashScopeASRConfig:
    api_key: str = _DASHSCOPE_API_KEY
    model: str = os.environ.get("DASHSCOPE_ASR_MODEL", "").strip()


@dataclass
class WhisperConfig:
    model: str = os.environ.get("WHISPER_MODEL", "").strip()
    device: str = os.environ.get("WHISPER_DEVICE", "").strip()
    compute_type: str = os.environ.get("WHISPER_COMPUTE_TYPE", "").strip()
    language: str = os.environ.get("WHISPER_LANGUAGE", "").strip()


@dataclass
class DashScopeTTSConfig:
    api_key: str = _DASHSCOPE_API_KEY
    model: str = os.environ.get("DASHSCOPE_TTS_MODEL", "").strip()


@dataclass
class DoubaoTTSConfig:
    appid: str = os.environ.get("DOUBAO_TTS_APPID", "").strip()
    access_token: str = os.environ.get("DOUBAO_TTS_ACCESS_TOKEN", "").strip()
    cluster: str = os.environ.get("DOUBAO_TTS_CLUSTER", "").strip()
    voice: str = os.environ.get("DOUBAO_TTS_VOICE", "").strip()
    encoding: str = os.environ.get("DOUBAO_TTS_ENCODING", "").strip()


@dataclass
class MiMoTTSConfig:
    api_key: str = os.environ.get("MIMO_API_KEY", "").strip()
    model: str = os.environ.get("MIMO_TTS_MODEL", "").strip()
    voice: str = os.environ.get("MIMO_TTS_VOICE", "").strip()
    format: str = os.environ.get("MIMO_TTS_FORMAT", "").strip()


@dataclass
class VoiceProviderConfig:
    doubao_asr: DoubaoASRConfig = field(default_factory=DoubaoASRConfig)
    aliyun_nls: AliyunNLSConfig = field(default_factory=AliyunNLSConfig)
    dashscope_asr: DashScopeASRConfig = field(default_factory=DashScopeASRConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    dashscope_tts: DashScopeTTSConfig = field(default_factory=DashScopeTTSConfig)
    doubao_tts: DoubaoTTSConfig = field(default_factory=DoubaoTTSConfig)
    mimo: MiMoTTSConfig = field(default_factory=MiMoTTSConfig)


VOICE = VoiceConfig()
VOICEPRINT = VoiceprintConfig()
VOICE_PROVIDERS = VoiceProviderConfig()
