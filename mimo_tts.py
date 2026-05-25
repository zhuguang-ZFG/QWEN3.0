#!/usr/bin/env python3
"""MiMo TTS client for Telegram voice replies."""
import base64
import logging
import os
import subprocess

import httpx

log = logging.getLogger(__name__)

API_BASE = "https://api.xiaomimimo.com"
API_KEY = os.environ.get("MIMO_TTS_KEY", "")
DEFAULT_MODEL = "mimo-v2.5-tts"
GFW_PROXY = os.environ.get("GFW_PROXY", "http://127.0.0.1:7897")


def _httpx_proxy() -> str | None:
    if os.environ.get("LIMA_WEIXIN_VPS", "").strip() in ("1", "true", "yes"):
        return None
    p = (os.environ.get("GFW_PROXY") or GFW_PROXY or "").strip()
    return p or None


async def tts(text: str, model: str = DEFAULT_MODEL) -> bytes | None:
    """Convert text to WAV bytes. Return None on failure."""
    api_key = os.environ.get("MIMO_TTS_KEY", API_KEY)
    if not api_key:
        log.warning("MIMO_TTS_KEY is not configured")
        return None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Read this aloud"},
            {"role": "assistant", "content": text},
        ],
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(proxy=_httpx_proxy(), timeout=30.0) as client:
            resp = await client.post(
                f"{API_BASE}/v1/chat/completions", headers=headers, json=body
            )
            if resp.status_code != 200:
                log.warning(f"MiMo TTS {resp.status_code}: {resp.text[:100]}")
                return None
            data = resp.json()
            audio = data["choices"][0]["message"].get("audio", {})
            raw = audio.get("data", "")
            if not raw:
                return None
            return base64.b64decode(raw)
    except Exception as e:
        log.error(f"MiMo TTS error: {e}")
        return None


async def tts_ogg(text: str, model: str = DEFAULT_MODEL) -> bytes | None:
    """Convert text to OGG Opus bytes for Telegram voice replies."""
    wav = await tts(text, model)
    if not wav:
        return None
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "48k",
             "-vbr", "on", "-f", "ogg", "pipe:1"],
            input=wav, capture_output=True, timeout=15,
        )
        if proc.returncode != 0:
            log.warning(f"ffmpeg failed: {proc.stderr[:200]}")
            return None
        return proc.stdout
    except FileNotFoundError:
        log.warning("ffmpeg not found, returning raw WAV")
        return wav
    except Exception as e:
        log.error(f"tts_ogg conversion error: {e}")
        return None
