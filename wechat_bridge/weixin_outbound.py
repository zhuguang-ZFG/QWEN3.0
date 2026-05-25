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


def _strip_for_tts(text: str) -> str:
    t = re.sub(r"\(?\d+/\d+\)\n?", "", text)
    t = re.sub(r"https?://\S+", "", t)
    return t.strip()[:480]


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
    from gateway.platforms.weixin import PlatformConfig, WeixinAdapter, send_weixin_direct

    text = str(reply.get("text") or "").strip()
    parts = split_fn(text, chunk=chunk) if text else []

    media_files: List[Tuple[str, bool]] = []
    temps: List[str] = []

    if reply.get("send_invite_qr"):
        try:
            from wechat_bridge.invite_qr import fetch_invite_qr_png

            got = await fetch_invite_qr_png()
            if got:
                data, mime = got
                ext = ".png" if "png" in mime else ".jpg"
                path = _write_temp(data, ext)
                temps.append(path)
                media_files.append((path, False))
            else:
                log.warning("invite QR image unavailable")
        except Exception as exc:
            log.warning("invite QR failed: %s", exc)

    voice_text = str(reply.get("voice_reply_text") or "").strip()
    if voice_text:
        vpath = await _synthesize_voice_file(_strip_for_tts(voice_text))
        if vpath:
            temps.append(vpath)
            media_files.append((vpath, True))

    account_id = str(extra.get("account_id") or "").strip()
    base_url = str(extra.get("base_url") or "").strip()
    cdn_base_url = str(extra.get("cdn_base_url") or "").strip()

    adapter = _adapter_for_session(
        session,
        token=token,
        extra=extra,
        account_id=account_id,
        base_url=base_url,
        cdn_base_url=cdn_base_url,
    )

    try:
        for idx, part in enumerate(parts):
            if idx > 0:
                await asyncio.sleep(0.35)
            if adapter:
                result = await adapter.send(chat_id, part[:4000])
                if not result.success:
                    await send_weixin_direct(
                        extra=extra,
                        token=token,
                        chat_id=chat_id,
                        message=part[:4000],
                    )
            else:
                await send_weixin_direct(
                    extra=extra,
                    token=token,
                    chat_id=chat_id,
                    message=part[:4000],
                )

        for path, is_voice in media_files:
            if adapter:
                await _deliver_file(adapter, chat_id, path, is_voice)
            else:
                await send_weixin_direct(
                    extra=extra,
                    token=token,
                    chat_id=chat_id,
                    message="",
                    media_files=[(path, is_voice)],
                )
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


async def _synthesize_voice_file(text: str) -> Optional[str]:
    if not text:
        return None
    try:
        import mimo_tts

        ogg = await mimo_tts.tts_ogg(text)
        if not ogg:
            return None
        return _write_temp(ogg, ".ogg")
    except Exception as exc:
        log.warning("voice TTS failed: %s", exc)
        return None


def _adapter_for_session(session, *, token: str, extra: dict, account_id: str, base_url: str, cdn_base_url: str):
    try:
        from gateway.platforms.weixin import WeixinAdapter, PlatformConfig
        from gateway.platforms.helpers import ContextTokenStore
        from hermes_constants import get_hermes_home

        adapter = WeixinAdapter(
            PlatformConfig(
                enabled=True,
                token=token,
                extra={**extra, "account_id": account_id, "base_url": base_url, "cdn_base_url": cdn_base_url},
            )
        )
        adapter._send_session = session
        adapter._session = session
        adapter._token = token
        adapter._account_id = account_id
        adapter._base_url = base_url
        adapter._cdn_base_url = cdn_base_url
        adapter._token_store = ContextTokenStore(str(get_hermes_home()))
        return adapter
    except Exception as exc:
        log.debug("adapter setup failed: %s", exc)
        return None


async def _deliver_file(adapter, chat_id: str, path: str, is_voice: bool) -> None:
    ext = Path(path).suffix.lower()
    _AUDIO = {".ogg", ".opus", ".mp3", ".wav", ".m4a", ".silk"}
    _IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    try:
        if is_voice or ext in _AUDIO:
            await adapter.send_voice(chat_id=chat_id, audio_path=path)
        elif ext in _IMAGE:
            await adapter.send_image_file(chat_id=chat_id, image_path=path)
        else:
            await adapter.send_document(chat_id=chat_id, file_path=path)
    except Exception as exc:
        log.warning("media deliver failed %s: %s", path, exc)
