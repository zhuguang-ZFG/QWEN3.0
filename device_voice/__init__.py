"""LiMa Device Voice Pipeline — ASR / TTS / VAD / voiceprint.

Provider-based architecture ported from xiaozhi-server, simplified for
LiMa's async-first FastAPI runtime.

Configuration via environment variables:
    LIMA_VOICE_ASR_PROVIDER=funasr|aliyun|aliyun_fallback|doubao|dashscope|whisper (default: funasr)
    LIMA_VOICE_TTS_PROVIDER=edge|doubao|aliyun|dashscope|mimo                     (default: edge)
    LIMA_VOICE_VAD_PROVIDER=silero                  (default: silero)
    LIMA_VOICE_ENABLED=1                            (default: 0)
    LIMA_VOICEPRINT_MODE=local|api|off               (default: local)
"""

from __future__ import annotations

import logging

from config.settings import VOICE as _voice_settings
from config.settings import VOICEPRINT as _voiceprint_settings

_log = logging.getLogger(__name__)

VOICE_ENABLED = _voice_settings.enabled
ASR_PROVIDER = _voice_settings.asr_provider
TTS_PROVIDER = _voice_settings.tts_provider
VAD_PROVIDER = _voice_settings.vad_provider
VOICEPRINT_MODE = _voiceprint_settings.mode

# Lazy-loaded singletons
_asr_instance = None
_tts_instance = None
_vad_instance = None
_voiceprint_instance = None


def get_asr_provider():
    """Return the configured ASR provider instance (lazy-loaded)."""
    global _asr_instance
    if _asr_instance is not None:
        return _asr_instance
    from device_voice.asr import create_asr_provider

    _asr_instance = create_asr_provider(ASR_PROVIDER)
    _log.info("ASR provider loaded: %s", ASR_PROVIDER)
    return _asr_instance


def get_tts_provider():
    """Return the configured TTS provider instance (lazy-loaded)."""
    global _tts_instance
    if _tts_instance is not None:
        return _tts_instance
    from device_voice.tts import create_tts_provider

    _tts_instance = create_tts_provider(TTS_PROVIDER)
    _log.info("TTS provider loaded: %s", TTS_PROVIDER)
    return _tts_instance


def get_vad_provider():
    """Return the configured VAD provider instance (lazy-loaded)."""
    global _vad_instance
    if _vad_instance is not None:
        return _vad_instance
    from device_voice.vad import create_vad_provider

    _vad_instance = create_vad_provider(VAD_PROVIDER)
    _log.info("VAD provider loaded: %s", VAD_PROVIDER)
    return _vad_instance


def get_voiceprint_provider():
    """Return the singleton VoiceprintProvider instance (lazy-loaded).

    The provider handles 3D-Speaker model loading, embedding extraction,
    and speaker identification. By default uses local mode with optional
    GPU acceleration. Falls back to API mode if configured.
    """
    global _voiceprint_instance
    if _voiceprint_instance is not None:
        return _voiceprint_instance
    from device_voice.voiceprint import get_voiceprint_provider as _get

    _voiceprint_instance = _get()
    _log.info("Voiceprint provider loaded")
    return _voiceprint_instance


def self_check() -> dict:
    """Verify each configured voice provider can be instantiated.

    Returns a dict mapping component name to ``"ok"`` or an error string.
    When voice is disabled all components report ``"disabled"``.
    """
    results = {"asr": "ok", "tts": "ok", "vad": "ok", "voiceprint": "ok"}
    if not VOICE_ENABLED:
        return {k: "disabled" for k in results}

    for key, loader in (
        ("asr", get_asr_provider),
        ("tts", get_tts_provider),
        ("vad", get_vad_provider),
    ):
        try:
            loader()
        except Exception as exc:  # noqa: BLE001
            _log.warning("Voice %s provider failed self-check: %s", key, exc)
            results[key] = str(exc)

    if VOICEPRINT_MODE != "off":
        try:
            get_voiceprint_provider()
        except Exception as exc:  # noqa: BLE001
            _log.warning("Voiceprint provider failed self-check: %s", exc)
            results["voiceprint"] = str(exc)
    else:
        results["voiceprint"] = "off"

    return results
