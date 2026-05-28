"""
Voice Gateway for LiMa AI
Real-time voice interaction via WebSocket:
  Browser mic → WebSocket → Whisper STT → LiMa Router → Edge-TTS → audio stream back

Dependencies: pip install fastapi uvicorn websockets edge-tts httpx python-multipart
"""

import os
import io
import re
import json
import logging
from typing import Optional

import httpx
import uvicorn
import edge_tts
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("voice_gateway")

app = FastAPI(title="LiMa Voice Gateway")

# --- Configuration ---
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LIMA_ROUTER_URL = os.getenv("LIMA_ROUTER_URL", "http://127.0.0.1:8090/v1/chat/completions")

STT_TIMEOUT = 10.0
LLM_TIMEOUT = 30.0

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？.!?\n])")

TTS_VOICES = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-AriaNeural",
}


def detect_language(text: str) -> str:
    chinese_chars = sum(1 for c in text if "一" <= c <= "鿿")
    return "zh" if chinese_chars > len(text) * 0.3 else "en"


# --- STT ---

async def transcribe_audio(audio_bytes: bytes, language: str = "zh") -> Optional[str]:
    """Transcribe audio using SiliconFlow Whisper, fallback to Groq."""
    text = await _stt_siliconflow(audio_bytes, language)
    if text is None and GROQ_API_KEY:
        text = await _stt_groq(audio_bytes, language)
    return text


async def _stt_siliconflow(audio_bytes: bytes, language: str) -> Optional[str]:
    if not SILICONFLOW_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=STT_TIMEOUT) as client:
            resp = await client.post(
                "https://api.siliconflow.cn/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {SILICONFLOW_API_KEY}"},
                files={"file": ("audio.webm", audio_bytes, "audio/webm")},
                data={"model": "FunAudioLLM/SenseVoiceSmall", "language": language},
            )
            if resp.status_code == 200:
                return resp.json().get("text", "").strip()
            logger.warning("SiliconFlow STT failed: %d %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("SiliconFlow STT error: %s", e)
    return None


async def _stt_groq(audio_bytes: bytes, language: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=STT_TIMEOUT) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": ("audio.webm", audio_bytes, "audio/webm")},
                data={"model": "whisper-large-v3", "language": language},
            )
            if resp.status_code == 200:
                return resp.json().get("text", "").strip()
            logger.warning("Groq STT failed: %d %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("Groq STT error: %s", e)
    return None


# --- TTS ---

async def generate_tts(text: str, language: str = "zh") -> bytes:
    """Generate TTS audio bytes (mp3) using edge-tts."""
    voice = TTS_VOICES.get(language, TTS_VOICES["zh"])
    communicate = edge_tts.Communicate(text, voice)
    audio_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data = chunk.get("data")
            if isinstance(audio_data, bytes):
                audio_buffer.write(audio_data)
    return audio_buffer.getvalue()


def split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries."""
    parts = SENTENCE_SPLIT_RE.split(text)
    return [p for p in parts if p.strip()]


# --- LLM Streaming ---

async def stream_llm_response(
    user_text: str,
    ws: WebSocket,
    language: str = "zh",
):
    """Stream LLM response, generate TTS per sentence, send both text and audio."""
    messages = [
        {"role": "user", "content": user_text},
    ]
    payload = {
        "model": "auto",
        "messages": messages,
        "stream": True,
    }

    buffer = ""
    full_response = ""

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                LIMA_ROUTER_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    logger.error("LLM error: %d %s", resp.status_code, error_body[:300])
                    await ws.send_json({"type": "error", "text": "LLM request failed"})
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

                    if not content:
                        continue

                    buffer += content
                    full_response += content

                    # Send text update
                    await ws.send_json({
                        "type": "response",
                        "text": content,
                        "done": False,
                    })

                    # Check for sentence boundaries
                    sentences = split_sentences(buffer)
                    if len(sentences) > 1:
                        # All but last are complete sentences
                        for sentence in sentences[:-1]:
                            if sentence.strip():
                                lang = detect_language(sentence) if language == "auto" else language
                                audio = await generate_tts(sentence.strip(), lang)
                                if audio:
                                    await ws.send_bytes(audio)
                        buffer = sentences[-1]

    except httpx.TimeoutException:
        logger.warning("LLM request timed out")
        await ws.send_json({"type": "error", "text": "LLM timeout"})
        return
    except Exception as e:
        logger.error("LLM streaming error: %s", e)
        await ws.send_json({"type": "error", "text": f"LLM error: {e}"})
        return

    # Flush remaining buffer
    if buffer.strip():
        lang = detect_language(buffer) if language == "auto" else language
        audio = await generate_tts(buffer.strip(), lang)
        if audio:
            await ws.send_bytes(audio)

    # Signal completion
    await ws.send_json({"type": "response", "text": "", "done": True})


# --- WebSocket Endpoint ---

@app.websocket("/ws/voice")
async def voice_ws(ws: WebSocket):
    await ws.accept()
    language = "zh"
    audio_buffer = bytearray()
    logger.info("WebSocket client connected")

    try:
        while True:
            message = await ws.receive()

            if message.get("type") == "websocket.disconnect":
                break

            # Handle binary audio data
            if "bytes" in message and message["bytes"]:
                audio_buffer.extend(message["bytes"])
                continue

            # Handle text messages (JSON)
            if "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")

                if msg_type == "config":
                    language = data.get("language", "zh")
                    logger.info("Client config: language=%s", language)
                    continue

                if msg_type == "end_audio":
                    # Client signals end of audio recording
                    if not audio_buffer:
                        await ws.send_json({"type": "error", "text": "No audio received"})
                        continue

                    audio_bytes = bytes(audio_buffer)
                    audio_buffer.clear()
                    logger.info("Received audio: %d bytes", len(audio_bytes))

                    # STT
                    transcript = await transcribe_audio(audio_bytes, language)
                    if not transcript:
                        await ws.send_json({"type": "error", "text": "Transcription failed"})
                        continue

                    logger.info("Transcript: %s", transcript[:100])
                    await ws.send_json({"type": "transcript", "text": transcript})

                    # LLM + TTS streaming
                    await stream_llm_response(transcript, ws, language)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        try:
            await ws.close()
        except Exception as exc:
            logger.debug("websocket close skipped: %s", type(exc).__name__)


# --- Health Check ---

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "service": "lima-voice-gateway"})


# --- Entry Point ---

if __name__ == "__main__":
    uvicorn.run(
        "voice_gateway:app",
        host="0.0.0.0",
        port=8091,
        log_level="info",
    )
