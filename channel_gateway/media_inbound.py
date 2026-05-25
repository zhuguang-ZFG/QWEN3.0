"""Inbound media: voice STT, file text extract, image vision summary."""

from __future__ import annotations

import base64
import os
import re
from typing import Any, List, Optional

_MAX_BYTES = int(os.environ.get("LIMA_CHANNEL_MEDIA_MAX_BYTES", str(1_500_000)))
_TEXT_EXTS = frozenset({
    ".txt", ".md", ".py", ".json", ".csv", ".log", ".xml", ".html", ".htm",
    ".yaml", ".yml", ".ini", ".cfg", ".toml",
})


def _max_b64_payload() -> int:
    return _MAX_BYTES


def _decode_attachment(att: dict) -> Optional[bytes]:
    raw = att.get("data_b64") or ""
    if not raw:
        return None
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception:
        return None
    if len(data) > _MAX_BYTES:
        return None
    return data


def _stt_audio(
    data: bytes,
    mime: str,
    language: str = "zh",
    *,
    filename: str = "",
) -> Optional[str]:
    try:
        import mimo_stt

        text = mimo_stt.transcribe_bytes(
            data, mime, name=filename or ("audio.silk" if "silk" in mime else "audio.wav")
        )
        if text:
            return text
    except ImportError:
        pass
    except Exception:
        pass

    import httpx

    groq = os.environ.get("GROQ_API_KEY", "").strip()
    sf = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    fname = filename or ("audio.silk" if "silk" in mime else "audio.webm")
    ctype = mime or "application/octet-stream"

    def _post(url: str, headers: dict, model: str, field: str) -> Optional[str]:
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(
                    url,
                    headers=headers,
                    files={"file": (fname, data, ctype)},
                    data={"model": model, "language": language},
                )
                if resp.status_code == 200:
                    return (resp.json().get("text") or "").strip()
        except Exception:
            return None
        return None

    if sf:
        t = _post(
            "https://api.siliconflow.cn/v1/audio/transcriptions",
            {"Authorization": f"Bearer {sf}"},
            "FunAudioLLM/SenseVoiceSmall",
            "file",
        )
        if t:
            return t
    if groq:
        return _post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            {"Authorization": f"Bearer {groq}"},
            "whisper-large-v3",
            "file",
        )
    return None


def _read_text_file(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext not in _TEXT_EXTS:
        return ""
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(enc)[:12000]
        except Exception:
            continue
    return ""


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages[:8]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)[:12000]
    except Exception:
        return ""


def _vision_summary(data: bytes, mime: str, user_note: str) -> str:
    import routing_engine
    import http_caller

    b64 = base64.b64encode(data).decode("ascii")
    media = mime or "image/jpeg"
    url = f"data:{media};base64,{b64}"
    prompt = user_note.strip() or "请用中文描述图片内容，若是文档/题目请概括要点。"
    messages = [
        {
            "role": "system",
            "content": (
                "你是 LiMa 助手，为微信访客分析图片。"
                "简洁中文，不透露内部架构。"
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        },
    ]
    try:
        result = routing_engine.route(
            prompt,
            messages,
            call_fn=http_caller.call_api,
            channel_role="guest",
        )
        answer = getattr(result, "answer", "") if hasattr(result, "answer") else str(result)
        return answer.strip() or "未能识别图片内容。"
    except Exception:
        return "图片分析暂时不可用，请稍后重试或改用文字描述。"


def _summarize_document(filename: str, excerpt: str, user_note: str) -> str:
    if not excerpt.strip():
        return (
            f"已收到文件「{filename}」，暂不支持该格式自动解析。\n"
            "请发送 .txt/.md/.pdf 或截图，并附上你想问的问题。"
        )
    import routing_engine
    import http_caller

    prompt = user_note.strip() or "请用中文概括以下文件要点，并给出可操作建议："
    body = excerpt[:8000]
    messages = [
        {
            "role": "system",
            "content": "你是 LiMa 助手，为微信访客分析文件内容。简洁中文。",
        },
        {"role": "user", "content": f"{prompt}\n\n---\n{body}"},
    ]
    try:
        result = routing_engine.route(
            prompt,
            messages,
            call_fn=http_caller.call_api,
            channel_role="guest",
        )
        answer = getattr(result, "answer", "") if hasattr(result, "answer") else str(result)
        head = f"【文件：{filename}】\n"
        return head + (answer.strip() or "未能生成摘要。")
    except Exception:
        return f"【文件：{filename}】\n已提取正文，但摘要服务暂不可用。正文前 500 字：\n{body[:500]}"


def extract_voice_transcript(text: str, attachments: Optional[List[dict]]) -> str:
    """Best-effort transcript for user-visible voice feedback."""
    for att in attachments or []:
        if str(att.get("kind") or "") == "voice":
            hint = str(att.get("transcript_hint") or "").strip()
            if hint:
                return hint[:500]
    m = re.search(r"\[语音转写\]\s*(.+?)(?:\n\n|\Z)", text or "", re.DOTALL)
    if m:
        return m.group(1).strip()[:500]
    return ""


def resolve_media_to_text(text: str, attachments: Optional[List[dict]]) -> str:
    """Merge plain text with voice/file/image attachments into one chat prompt."""
    if not attachments:
        return (text or "").strip()

    parts: List[str] = []
    base = (text or "").strip()
    if base:
        parts.append(base)

    for att in attachments:
        kind = str(att.get("kind") or "")
        if kind == "voice":
            hint = str(att.get("transcript_hint") or "").strip()
            data = _decode_attachment(att)
            transcript = hint
            if not transcript and data:
                transcript = _stt_audio(
                    data,
                    str(att.get("mime") or "audio/silk"),
                    filename=str(att.get("filename") or "voice.silk"),
                ) or ""
            if transcript:
                parts.append(f"[语音转写] {transcript}")
            else:
                parts.append("[语音消息] 未能识别，请重试或改用文字。")
        elif kind == "image":
            data = _decode_attachment(att)
            if not data:
                parts.append("[图片] 下载失败或超过大小限制。")
                continue
            note = base or "请分析这张图片"
            parts.append(_vision_summary(data, str(att.get("mime") or "image/jpeg"), note))
        elif kind == "file":
            data = _decode_attachment(att)
            fname = str(att.get("filename") or "file")
            if not data:
                parts.append(f"[文件 {fname}] 无法读取或超过大小限制（{_MAX_BYTES // 1024}KB）。")
                continue
            excerpt = _read_text_file(fname, data)
            if not excerpt and fname.lower().endswith(".pdf"):
                excerpt = _pdf_text(data)
            parts.append(_summarize_document(fname, excerpt, base))
        else:
            parts.append(f"[附件 {kind}] 暂不支持。")

    return "\n\n".join(p for p in parts if p).strip()
