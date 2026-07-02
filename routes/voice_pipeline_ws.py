"""Self-hosted real-time voice pipeline WebSocket.

Browsers connect to ``/v1/voice`` and stream raw PCM audio (16 kHz, 16-bit,
mono). LiMa runs VAD → ASR → LLM → TTS on the server and streams the
synthesized audio back. This provides a fallback when Gemini Live / OpenAI
Realtime are unavailable.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from routes.ws_common import _client_ip_from_websocket

from access_guard import (
    WS_QUERY_PARAM_TOKEN_WARNING,
    authenticate_websocket,
    configured_api_keys,
    extract_bearer_token,
    is_token_valid,
)
import ws_ticket
from device_voice.dialogue import process_text_utterance, process_voice_utterance
from device_voice.vad import VADState, create_vad_provider

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")

FRAME_BYTES = 1024  # 512 samples @ 16-bit mono 16kHz


@router.post("/voice/ticket")
async def issue_voice_ws_ticket(request) -> JSONResponse:  # type: ignore  # noqa: ANN001
    """Exchange a configured private API key for a one-time voice WS ticket."""
    from routes.json_body import read_json_object

    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    header_token = extract_bearer_token(request.headers.get("authorization", ""))
    token = header_token or str(body.get("token", "")).strip()
    if not is_token_valid(token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return JSONResponse(
        {
            "ticket": ws_ticket.issue(),
            "expires_in": ws_ticket.TTL_SECONDS,
        }
    )


@router.websocket("/voice")
async def voice_pipeline_ws(
    websocket: WebSocket,
    authorization: str = Query(default=""),
) -> None:
    """Browser → LiMa → ASR → LLM → TTS → browser audio loop."""
    authorized, auth_method = authenticate_websocket(websocket, authorization)
    if auth_method == "query":
        _log.warning(WS_QUERY_PARAM_TOKEN_WARNING, websocket.url.path)
    if not authorized:
        if not configured_api_keys():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LiMa private API key is not configured."
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        vad = create_vad_provider("silero")
    except Exception as exc:  # pragma: no cover - defensive startup
        _log.warning("Silero VAD unavailable (%s); falling back to energy VAD", exc)
        vad = _SimpleEnergyVAD()

    await websocket.accept()
    session = _VoiceSession(websocket, vad)
    try:
        await session.run()
    except WebSocketDisconnect:
        _log.debug("voice pipeline client disconnected")
    finally:
        await session.close()


class _VoiceSession:
    """Manage one browser voice session: VAD buffering + pipeline queue."""

    def __init__(self, websocket: WebSocket, vad: Any) -> None:
        self.websocket = websocket
        self.vad = vad
        self.vad_state = VADState()
        self.pending = bytearray()
        self.queue: asyncio.Queue[bytes | str] = asyncio.Queue()
        self.worker_task: asyncio.Task | None = None
        self.closed = False

    async def run(self) -> None:
        self.worker_task = asyncio.create_task(self._worker())
        await self._send_status("listening")
        while True:
            message = await self.websocket.receive()
            if isinstance(message, bytes):
                await self._handle_audio(message)
            elif isinstance(message, dict):
                if message.get("type") == "websocket.disconnect":
                    break
                if "text" in message:
                    await self._handle_message(message["text"])
                elif "bytes" in message:
                    await self._handle_audio(message["bytes"])

    async def _handle_message(self, text: str) -> None:
        try:
            payload = json.loads(text)
        except Exception:
            await self._send_error("E_INVALID_JSON", "invalid JSON frame")
            return
        msg_type = payload.get("type")
        if msg_type == "audio":
            data = payload.get("data", "")
            try:
                pcm = base64.b64decode(data)
            except Exception:
                await self._send_error("E_INVALID_AUDIO", "invalid base64 audio")
                return
            await self._handle_audio(pcm)
        elif msg_type == "text":
            user_text = payload.get("text", "").strip()
            if user_text:
                await self.queue.put(user_text)
        else:
            await self._send_error("E_UNKNOWN_TYPE", f"unknown frame type: {msg_type}")

    async def _handle_audio(self, pcm: bytes) -> None:
        self.pending.extend(pcm)
        while len(self.pending) >= FRAME_BYTES:
            frame = bytes(self.pending[:FRAME_BYTES])
            self.pending[:FRAME_BYTES] = b""
            try:
                self.vad.detect(frame, self.vad_state)
            except Exception as exc:
                _log.warning("VAD detection error: %s", exc)
                continue
            if self.vad.is_utterance_end(self.vad_state):
                utterance = bytes(self.vad_state.speech_buffer)
                self.vad.reset(self.vad_state)
                if utterance:
                    await self.queue.put(utterance)

    async def _worker(self) -> None:
        while not self.closed:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                if isinstance(item, bytes):
                    await self._process_utterance(item)
                else:
                    await self._process_text(item)
            except Exception as exc:
                _log.warning("Voice pipeline worker error: %s", exc, exc_info=True)
                await self._send_status("idle")

    async def _process_utterance(self, pcm: bytes) -> None:
        await self._send_status("thinking")
        client_ip = _client_ip_from_websocket(self.websocket)
        result = await process_voice_utterance(pcm, device_id="voice-web", client_ip=client_ip)
        await self._emit_result(result)

    async def _process_text(self, text: str) -> None:
        await self._send_status("thinking")
        result = await process_text_utterance(text, device_id="voice-web")
        await self._emit_result(result)

    async def _emit_result(self, result: dict[str, Any]) -> None:
        transcript = result.get("transcript", "")
        reply_text = result.get("reply_text", "")
        reply_audio = result.get("reply_audio", b"")
        if transcript:
            await self._send_json({"type": "transcript", "text": transcript})
        if reply_text:
            await self._send_status("speaking", transcript=reply_text)
            await self._send_json({"type": "reply", "text": reply_text})
        if reply_audio:
            await self._send_audio_chunks(reply_audio)
        await self._send_status("listening")

    async def _send_audio_chunks(self, audio: bytes, chunk_size: int = 48000) -> None:
        """Stream large PCM replies as multiple small JSON frames."""
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            await self._send_json(
                {
                    "type": "audio",
                    "format": "pcm",
                    "sample_rate": 16000,
                    "data": base64.b64encode(chunk).decode("ascii"),
                }
            )

    async def _send_status(self, status: str, transcript: str = "") -> None:
        payload: dict[str, Any] = {"type": "status", "status": status}
        if transcript:
            payload["transcript"] = transcript
        await self._send_json(payload)

    async def _send_error(self, code: str, message: str) -> None:
        await self._send_json({"type": "error", "code": code, "message": message})

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if not self.closed:
            await self.websocket.send_json(payload)

    async def close(self) -> None:
        self.closed = True
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass


class _SimpleEnergyVAD:
    """Fallback VAD based on per-frame RMS energy.

    Used when the Silero ONNX model is not available. It is less robust to
    noise but works out-of-the-box for testing and low-noise environments.
    """

    _FRAME_BYTES = 1024  # 512 samples @ 16-bit mono 16kHz
    _FRAME_MS = 32

    def __init__(
        self,
        threshold: float = 0.015,
        silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 250,
    ) -> None:
        self._threshold = threshold
        self._silence_duration_ms = silence_duration_ms
        self._min_speech_frames = min_speech_duration_ms // self._FRAME_MS
        self._last_voice_time = 0.0

    def detect(self, audio_chunk: bytes, state: VADState) -> bool:
        import math
        import time

        offset = 0
        has_voice = False
        while offset + self._FRAME_BYTES <= len(audio_chunk):
            frame = audio_chunk[offset : offset + self._FRAME_BYTES]
            offset += self._FRAME_BYTES
            ints = [int.from_bytes(frame[i : i + 2], "little", signed=True) for i in range(0, len(frame), 2)]
            rms = math.sqrt(sum(v * v for v in ints) / len(ints)) / 32768.0
            is_voice = rms > self._threshold
            if is_voice:
                state.speech_buffer.extend(frame)
                state.is_speaking = True
                state.silence_frames = 0
                self._last_voice_time = time.monotonic() * 1000
                has_voice = True
            else:
                state.silence_frames += 1
        state.total_frames += 1
        return has_voice

    def is_utterance_end(self, state: VADState) -> bool:
        import time

        if not state.is_speaking:
            return False
        if len(state.speech_buffer) // self._FRAME_BYTES < self._min_speech_frames:
            return False
        return (time.monotonic() * 1000 - self._last_voice_time) >= self._silence_duration_ms

    def reset(self, state: VADState) -> None:
        state.is_speaking = False
        state.speech_buffer.clear()
        state.silence_frames = 0
