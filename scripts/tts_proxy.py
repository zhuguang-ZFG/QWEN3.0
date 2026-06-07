#!/usr/bin/env python3
"""Standalone MiMo TTS proxy for chat.donglicao.com.

Runs on port 8085, proxies to Xiaomi MiMo TTS API.
Endpoints:
  POST /tts       — text-to-speech, returns audio
  GET  /tts/voices — list available voices
"""
import base64
import logging
import os
import sys

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tts-proxy")

app = FastAPI(title="LiMa TTS Proxy")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ──────────────────────────────────────────────────────────────────
MIMO_API_BASE = os.environ.get("MIMO_API_BASE", "https://api.xiaomimimo.com")
MIMO_API_KEY = os.environ.get("MIMO_TTS_KEY", "") or os.environ.get("MIMO_V2_PRO_KEY", "")
DEFAULT_MODEL = "mimo-v2.5-tts"
PORT = int(os.environ.get("TTS_PORT", "8085"))

# Voice catalog
VOICES = [
    {"id": "冰糖", "name": "冰糖", "lang": "zh", "gender": "female", "desc": "温柔女声"},
    {"id": "茉莉", "name": "茉莉", "lang": "zh", "gender": "female", "desc": "甜美女声"},
    {"id": "苏打", "name": "苏打", "lang": "zh", "gender": "male", "desc": "清朗男声"},
    {"id": "白桦", "name": "白桦", "lang": "zh", "gender": "male", "desc": "沉稳男声"},
    {"id": "mimo_default", "name": "默认", "lang": "zh", "gender": "female", "desc": "系统默认"},
    {"id": "Mia", "name": "Mia", "lang": "en", "gender": "female", "desc": "English female"},
    {"id": "Chloe", "name": "Chloe", "lang": "en", "gender": "female", "desc": "English female"},
    {"id": "Milo", "name": "Milo", "lang": "en", "gender": "male", "desc": "English male"},
    {"id": "Dean", "name": "Dean", "lang": "en", "gender": "male", "desc": "English male"},
]


@app.get("/tts/voices")
async def list_voices():
    return JSONResponse({"voices": VOICES})


@app.post("/tts")
async def tts(request: Request):
    """Proxy text-to-speech to MiMo API."""
    if not MIMO_API_KEY:
        return JSONResponse({"error": "TTS service not configured"}, status_code=503)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)
    if len(text) > 2000:
        text = text[:2000]

    voice = body.get("voice", "冰糖")
    style = body.get("style", "")
    model = body.get("model", DEFAULT_MODEL)
    fmt = body.get("format", "wav")

    # Build MiMo messages
    user_content = style if style else "自然、流畅、清晰的语调。"
    messages = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": text},
    ]

    payload = {
        "model": model,
        "messages": messages,
        "audio": {"format": fmt, "voice": voice},
        "stream": False,
    }

    headers = {
        "api-key": MIMO_API_KEY,
        "Content-Type": "application/json",
    }

    log.info("TTS request: voice=%s model=%s text=%d chars", voice, model, len(text))

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{MIMO_API_BASE}/v1/chat/completions",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            log.warning("MiMo TTS %d: %s", resp.status_code, resp.text[:200])
            return JSONResponse(
                {"error": f"TTS upstream error {resp.status_code}"},
                status_code=502,
            )

        data = resp.json()
        audio_data = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("audio", {})
            .get("data", "")
        )

        if not audio_data:
            return JSONResponse({"error": "no audio data in response"}, status_code=502)

        audio_bytes = base64.b64decode(audio_data)

        content_type = "audio/wav"
        if fmt == "mp3":
            content_type = "audio/mpeg"
        elif fmt == "opus":
            content_type = "audio/opus"
        elif fmt == "pcm16":
            content_type = "audio/pcm"

        return Response(
            content=audio_bytes,
            media_type=content_type,
            headers={"Cache-Control": "no-cache"},
        )

    except httpx.TimeoutException:
        log.warning("MiMo TTS timeout")
        return JSONResponse({"error": "TTS request timed out"}, status_code=504)
    except Exception as e:
        log.error("TTS error: %s", e)
        return JSONResponse({"error": f"TTS error: {type(e).__name__}"}, status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "tts-proxy", "key_configured": bool(MIMO_API_KEY)}


if __name__ == "__main__":
    log.info("Starting TTS proxy on port %d (API: %s)", PORT, MIMO_API_BASE)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
