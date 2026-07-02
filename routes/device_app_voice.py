"""Device app voice routes (M0): ASR transcription + intent resolution + WS ticket.

薄包装现有 device_voice.get_asr_provider() 与 device_gateway.intent.resolve_voice_task。
本端点只做「转写 + 意图解析」，不创建任务 —— 前端确认后才调用 v2SubmitTask 派发，
避免误识别直接驱动物理机器（确认对话框是强制人工关卡）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, UploadFile
from fastapi.responses import JSONResponse

import ws_ticket
from device_gateway.intent import resolve_voice_task
from device_logic.auth import authorize
from device_logic.http import err
from device_voice import get_asr_provider

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/device/v1/app", tags=["device-app-voice"])

# 约 30s @ 16kHz 16-bit mono ≈ 1MB；留余量到 5MB。
MAX_AUDIO_BYTES = 5 * 1024 * 1024


def _to_pcm(audio_data: bytes) -> bytes:
    """剥掉 WAV RIFF header 取 raw PCM。

    ASRProvider.transcribe 期望 raw PCM（16-bit signed LE mono），直接传 WAV 会乱码。
    WAV 头长度不固定（可能含 LIST/fact 等额外块），因此动态定位 `data` 块：
    找到 `data` 标记后，PCM 紧跟在其后的 4 字节子块长度字段之后。
    若非 RIFF 数据则按已是 raw PCM 处理。
    """
    if audio_data[:4] != b"RIFF":
        return audio_data
    marker = audio_data.find(b"data")
    if marker == -1:
        return audio_data
    # data 标记(4) + 子块长度字段(4) 之后才是 PCM
    return audio_data[marker + 8 :]


@router.post("/voice/transcribe")
async def voice_transcribe(
    audio: UploadFile,
    authorization: str = Header(default=""),
) -> JSONResponse:
    """上传音频 → ASR 转写 + 意图解析。返回 {text, intent}，不派发任务。"""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    audio_data = await audio.read()
    if not audio_data:
        return err(400, "empty audio", 400)
    if len(audio_data) > MAX_AUDIO_BYTES:
        return err(413, f"audio exceeds {MAX_AUDIO_BYTES // 1024 // 1024}MB", 413)

    pcm_data = _to_pcm(audio_data)

    try:
        text = await get_asr_provider().transcribe(pcm_data, sample_rate=16000)
    except Exception as exc:  # 不静默降级：ASR 失败明确报错
        _log.warning("voice transcribe failed: %s", exc)
        # 不向客户端泄漏内部异常细节（可能含后端地址/堆栈）。
        return err(503, "asr transcription failed", 503)

    intent = resolve_voice_task(text)
    return JSONResponse({"code": 0, "data": {"text": text, "intent": intent}})


@router.post("/voice/ticket")
async def voice_ticket(authorization: str = Header(default="")) -> JSONResponse:
    """签发一次性 WS ticket，供小程序实时流连接 /v1/voice?ticket=… 使用。"""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    return JSONResponse({"code": 0, "data": {"ticket": ws_ticket.issue(), "expires_in": ws_ticket.TTL_SECONDS}})
