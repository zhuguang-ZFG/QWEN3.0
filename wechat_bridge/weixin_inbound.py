"""Collect Weixin iLink inbound text + media for LiMa channel."""

from __future__ import annotations

import base64
import os
from typing import Any, Dict, List, Tuple

_MAX = int(os.environ.get("LIMA_CHANNEL_MEDIA_MAX_BYTES", str(1_500_000)))


async def collect_weixin_message(
    session,
    message: Dict[str, Any],
    *,
    cdn_base_url: str,
) -> Tuple[str, List[dict]]:
    from gateway.platforms.weixin import (
        ITEM_FILE,
        ITEM_IMAGE,
        ITEM_VOICE,
        WEIXIN_CDN_BASE_URL,
        _download_and_decrypt_media,
        _extract_text,
        _media_reference,
        _mime_from_filename,
    )

    cdn = (cdn_base_url or WEIXIN_CDN_BASE_URL).rstrip("/")
    item_list = message.get("item_list") or []
    text = _extract_text(item_list)
    attachments: List[dict] = []

    for item in item_list:
        itype = item.get("type")
        if itype == ITEM_VOICE:
            voice = item.get("voice_item") or {}
            hint = str(voice.get("text") or "").strip()
            media = voice.get("media") or {}
            att: dict = {
                "kind": "voice",
                "mime": "audio/silk",
                "transcript_hint": hint,
            }
            if not hint:
                try:
                    data = await _download_and_decrypt_media(
                        session,
                        cdn_base_url=cdn,
                        encrypted_query_param=media.get("encrypt_query_param"),
                        aes_key_b64=media.get("aes_key"),
                        full_url=media.get("full_url"),
                        timeout_seconds=60.0,
                    )
                    if data and len(data) <= _MAX:
                        att["data_b64"] = base64.b64encode(data).decode("ascii")
                except Exception:
                    pass
            attachments.append(att)
        elif itype == ITEM_IMAGE:
            media = _media_reference(item, "image_item")
            try:
                img = item.get("image_item") or {}
                aes = img.get("aeskey")
                aes_b64 = (
                    base64.b64encode(bytes.fromhex(str(aes))).decode("ascii")
                    if aes
                    else media.get("aes_key")
                )
                data = await _download_and_decrypt_media(
                    session,
                    cdn_base_url=cdn,
                    encrypted_query_param=media.get("encrypt_query_param"),
                    aes_key_b64=aes_b64,
                    full_url=media.get("full_url"),
                    timeout_seconds=30.0,
                )
                if data and len(data) <= _MAX:
                    attachments.append({
                        "kind": "image",
                        "mime": "image/jpeg",
                        "data_b64": base64.b64encode(data).decode("ascii"),
                    })
            except Exception:
                attachments.append({"kind": "image", "error": "download_failed"})
        elif itype == ITEM_FILE:
            file_item = item.get("file_item") or {}
            media = file_item.get("media") or {}
            fname = str(file_item.get("file_name") or "document.bin")
            mime = _mime_from_filename(fname)
            try:
                data = await _download_and_decrypt_media(
                    session,
                    cdn_base_url=cdn,
                    encrypted_query_param=media.get("encrypt_query_param"),
                    aes_key_b64=media.get("aes_key"),
                    full_url=media.get("full_url"),
                    timeout_seconds=60.0,
                )
                if data and len(data) <= _MAX:
                    attachments.append({
                        "kind": "file",
                        "filename": fname,
                        "mime": mime,
                        "data_b64": base64.b64encode(data).decode("ascii"),
                    })
            except Exception:
                attachments.append({
                    "kind": "file",
                    "filename": fname,
                    "error": "download_failed",
                })

    if not text and attachments:
        kinds = [a.get("kind") for a in attachments]
        if "voice" in kinds:
            text = ""
        elif "image" in kinds:
            text = "[图片]"
        elif "file" in kinds:
            text = "[文件]"

    return text, attachments
