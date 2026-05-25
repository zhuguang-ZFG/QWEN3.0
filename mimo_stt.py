#!/usr/bin/env python3
"""MiMo speech-to-text via Xiaomi official API (same key as mimo_tts)."""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

API_BASE = "https://api.xiaomimimo.com/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("MIMO_STT_MODEL", "mimo-v2-omni")
GFW_PROXY = os.environ.get("GFW_PROXY", "http://127.0.0.1:7897")

_STT_SYSTEM = (
    "你是语音转写助手。请准确转写音频中的 spoken 内容，"
    "只输出转写文本，不要解释、不要标点以外的多余内容。"
)
_STT_USER = "请转写这段音频，只返回转写文字。"

_MIME_FOR_EXT = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


def _api_key() -> str:
    return (
        os.environ.get("MIMO_API_KEY", "").strip()
        or os.environ.get("MIMO_TTS_KEY", "").strip()
    )


def _enabled() -> bool:
    if os.environ.get("LIMA_MIMO_STT", "1") != "1":
        return False
    return bool(_api_key())


def _guess_mime(data: bytes, mime: str, name: str) -> str:
    if mime and mime != "application/octet-stream":
        return mime
    ext = Path(name or "").suffix.lower()
    return _MIME_FOR_EXT.get(ext, "audio/wav")


def _ffmpeg_to_wav(data: bytes, suffix: str) -> Optional[bytes]:
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as inp:
            inp.write(data)
            inp_path = inp.name
        out_path = inp_path + ".wav"
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-i", inp_path,
                "-ar", "16000", "-ac", "1", "-f", "wav", out_path,
            ],
            capture_output=True,
            timeout=25,
        )
        if proc.returncode != 0:
            log.debug("ffmpeg silk/amr convert failed: %s", proc.stderr[:200])
            return None
        wav = Path(out_path).read_bytes()
        return wav if wav else None
    except FileNotFoundError:
        log.debug("ffmpeg not installed for MiMo STT")
        return None
    except Exception as exc:
        log.debug("ffmpeg error: %s", exc)
        return None
    finally:
        for p in (locals().get("inp_path"), locals().get("out_path")):
            if p and os.path.isfile(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass


def _prepare_wav_bytes(data: bytes, mime: str, name: str = "") -> Optional[bytes]:
    mime_l = (mime or "").lower()
    if mime_l in _MIME_FOR_EXT.values() or mime_l.endswith("/wav"):
        if "silk" not in mime_l and not (name or "").endswith(".silk"):
            return data
    if "silk" in mime_l or (name or "").endswith(".silk"):
        converted = _ffmpeg_to_wav(data, ".silk")
        return converted
    if mime_l.endswith("/amr") or (name or "").endswith(".amr"):
        converted = _ffmpeg_to_wav(data, ".amr")
        return converted
    if mime_l in ("audio/webm", "audio/mpeg", "audio/mp4", "audio/ogg", "audio/flac"):
        converted = _ffmpeg_to_wav(data, Path(name or "a.bin").suffix or ".webm")
        return converted or data
    converted = _ffmpeg_to_wav(data, ".bin")
    return converted or data


def _extract_transcript(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    for key in ("content", "reasoning_content"):
        text = str(msg.get(key) or "").strip()
        if text:
            return text
    return ""


def transcribe_bytes(
    data: bytes,
    mime: str = "audio/wav",
    *,
    name: str = "audio.wav",
    language: str = "zh",
) -> Optional[str]:
    """Sync STT: MiMo audio understanding with transcription-only prompts."""
    if not _enabled() or not data:
        return None
    wav = _prepare_wav_bytes(data, mime, name)
    if not wav:
        return None
    audio_mime = "audio/wav"
    b64 = base64.b64encode(wav).decode("ascii")
    audio_data = f"data:{audio_mime};base64,{b64}"
    model = os.environ.get("MIMO_STT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    api_key = _api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "api-key": api_key,
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": _STT_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": audio_data}},
                    {
                        "type": "text",
                        "text": _STT_USER if language.startswith("zh") else (
                            "Transcribe the audio. Return transcription only."
                        ),
                    },
                ],
            },
        ],
        "max_completion_tokens": 1024,
        "temperature": 0,
    }
    proxy = os.environ.get("GFW_PROXY", GFW_PROXY).strip() or None
    try:
        with httpx.Client(proxy=proxy, timeout=45.0) as client:
            resp = client.post(API_BASE, headers=headers, json=body)
            if resp.status_code != 200:
                log.warning("MiMo STT %s: %s", resp.status_code, resp.text[:200])
                return None
            text = _extract_transcript(resp.json()).strip()
            return text or None
    except Exception as exc:
        log.warning("MiMo STT error: %s", exc)
        return None


async def transcribe_bytes_async(
    data: bytes,
    mime: str = "audio/wav",
    *,
    name: str = "audio.wav",
    language: str = "zh",
) -> Optional[str]:
    """Async wrapper for Telegram and other async callers."""
    import asyncio

    return await asyncio.to_thread(
        transcribe_bytes, data, mime, name=name, language=language
    )
