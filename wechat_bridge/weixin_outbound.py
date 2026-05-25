"""Deliver Channel Gateway reply dict over Weixin iLink (text + image + voice)."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# iLink 会静默丢弃 bot 方向 VOICE 气泡（HTTP 200 但客户端不显示）。
# 默认用可播放的 WAV 文件；设 LIMA_WEIXIN_VOICE_MODE=bubble 可实验 SILK 气泡。
_VOICE_MODE = os.environ.get("LIMA_WEIXIN_VOICE_MODE", "file").strip().lower()
_VOICE_FILE_CAPTION = os.environ.get("LIMA_WEIXIN_VOICE_FILE_CAPTION", "语音回复")


def _strip_for_tts(text: str) -> str:
    t = text
    for marker in ("——", "---"):
        if marker in t:
            t = t.split(marker, 1)[0]
    t = re.sub(r"\(?\d+/\d+\)\n?", "", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF]", "", t)
    return re.sub(r"\s+", " ", t).strip()[:480]


_LITEAPP_URL = re.compile(r"https://liteapp\.weixin\.qq\.com/q/\S+")


async def _ensure_invite_link_in_text(text: str, *, account_id: str = "") -> str:
    """Legacy hook: guest liteapp links do not route to our bot; keep body only."""
    del account_id
    if "liteapp 链接无效" in text or "不会进 LiMa" in text:
        return _LITEAPP_URL.sub("", text).strip()
    return text


async def deliver_channel_reply(
    *,
    session,
    extra: Dict[str, Any],
    token: str,
    chat_id: str,
    reply: dict,
    split_fn,
    chunk: int = 3600,
) -> None:
    """Send text chunks, optional invite QR image, optional voice attachment."""
    from gateway.platforms.weixin import send_weixin_direct
    from wechat_bridge.weixin_adapter import ensure_live_adapter

    invite_mode = bool(reply.get("send_invite_qr"))
    text = str(reply.get("text") or "").strip()
    if invite_mode:
        text = await _ensure_invite_link_in_text(
            text, account_id=str(extra.get("account_id") or "")
        )
    parts = split_fn(text, chunk=chunk) if text else []

    media_files: List[Tuple[str, bool]] = []
    temps: List[str] = []
    image_send_failed = False
    voice_path: Optional[str] = None

    if invite_mode:
        try:
            from channel_gateway.outbound_pack import invite_image_enabled
            from wechat_bridge.invite_qr import fetch_invite_qr_png

            got = None
            if invite_image_enabled():
                got = await fetch_invite_qr_png(
                    account_id=str(extra.get("account_id") or "")
                )
            if got:
                data, mime = got
                ext = ".png" if "png" in mime else ".jpg"
                path = _write_temp(data, ext)
                temps.append(path)
                media_files.append((path, False))
            else:
                log.warning("invite QR image unavailable (link still in text)")
        except Exception as exc:
            log.warning("invite QR failed: %s", exc)

    voice_text = str(reply.get("voice_reply_text") or "").strip()
    if voice_text:
        voice_path = await _synthesize_voice_reply(_strip_for_tts(voice_text))
        if voice_path:
            temps.append(voice_path)
        else:
            log.warning("voice reply skipped: TTS failed")

    account_id = str(extra.get("account_id") or "").strip()
    base_url = str(extra.get("base_url") or "").strip()
    cdn_base_url = str(extra.get("cdn_base_url") or "").strip()

    adapter = ensure_live_adapter(
        session=session,
        token=token,
        account_id=account_id,
        base_url=base_url,
        cdn_base_url=cdn_base_url,
        extra=extra,
    )

    try:
        if voice_path:
            ok = await _deliver_voice(adapter, chat_id, voice_path)
            if not ok:
                log.warning("voice outbound failed mode=%s", _VOICE_MODE)

        if invite_mode and media_files:
            for path, is_voice in media_files:
                if is_voice:
                    continue
                ok = await _deliver_file(adapter, chat_id, path, is_voice)
                if not ok:
                    image_send_failed = True
                    log.warning("invite QR image CDN send failed; user should use link in text")

        for idx, part in enumerate(parts):
            if idx > 0:
                await asyncio.sleep(0.35)
            result = await adapter.send(chat_id, part[:4000])
            if not result.success:
                await send_weixin_direct(
                    extra=extra,
                    token=token,
                    chat_id=chat_id,
                    message=part[:4000],
                )

        if image_send_failed and parts:
            hint = "（二维码图片未送达，请用上方的扫码链接添加。）"
            if hint not in parts[-1]:
                tail = parts[-1] + "\n" + hint
                await adapter.send(chat_id, tail[:4000])

        remaining = (
            [(p, v) for p, v in media_files if not (invite_mode and not v)]
            if invite_mode
            else media_files
        )
        for path, is_voice in remaining:
            await _deliver_file(adapter, chat_id, path, is_voice)
    finally:
        for p in temps:
            try:
                os.unlink(p)
            except OSError:
                pass


def _write_temp(data: bytes, ext: str) -> str:
    fd, path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    Path(path).write_bytes(data)
    return path


async def _synthesize_voice_reply(text: str) -> Optional[str]:
    """Return temp audio path (.wav for file mode, .silk for bubble mode)."""
    if not text:
        return None
    try:
        import mimo_tts

        wav = await mimo_tts.tts(text)
        if not wav:
            return None
        if _VOICE_MODE == "bubble":
            from wechat_bridge.voice_silk import wav_bytes_to_silk_path

            got = wav_bytes_to_silk_path(wav)
            if got:
                if isinstance(got, tuple):
                    silk_path, play_ms = got[0], int(got[1])
                else:
                    silk_path, play_ms = str(got), 3000
                log.info(
                    "voice silk ready bytes=%s playtime_ms=%s",
                    Path(silk_path).stat().st_size,
                    play_ms,
                )
                return silk_path
            log.warning("silk encode failed")
            return None
        wav_path = _write_temp(wav, ".wav")
        log.info("voice wav ready bytes=%s", len(wav))
        return wav_path
    except Exception as exc:
        log.warning("voice TTS failed: %s", exc)
        return None


async def _deliver_voice(adapter, chat_id: str, audio_path: str) -> bool:
    if _VOICE_MODE == "bubble" and audio_path.endswith(".silk"):
        try:
            from wechat_bridge.voice_silk import _duration_to_ms
            from wechat_bridge.weixin_voice_send import send_silk_voice_bubble

            play_ms = _duration_to_ms(0, audio_path)
            if await send_silk_voice_bubble(
                adapter, chat_id, audio_path, playtime_ms=play_ms
            ):
                return True
            log.warning("voice bubble not shown by WeChat; try LIMA_WEIXIN_VOICE_MODE=file")
        except Exception as exc:
            log.warning("voice bubble failed: %s", exc)
        return False
    return await _deliver_voice_file(adapter, chat_id, audio_path)


async def _deliver_voice_file(adapter, chat_id: str, wav_path: str) -> bool:
    """iLink 可靠路径：语音以文件形式送达（可点开播放）。"""
    try:
        mid = await adapter._send_file(
            chat_id,
            wav_path,
            _VOICE_FILE_CAPTION,
            force_file_attachment=True,
        )
        ok = bool(mid)
        log.info("voice file sent chat=%s ok=%s", chat_id[:12], ok)
        return ok
    except Exception as exc:
        log.warning("voice file send failed: %s", exc)
        return False


async def _deliver_file(adapter, chat_id: str, path: str, is_voice: bool) -> bool:
    ext = Path(path).suffix.lower()
    _IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    try:
        if ext in _IMAGE:
            result = await adapter.send_image_file(chat_id=chat_id, image_path=path)
            return bool(result.success)
        result = await adapter.send_document(chat_id=chat_id, file_path=path)
        return bool(result.success)
    except Exception as exc:
        log.warning("media deliver failed %s: %s", path, exc)
        return False
