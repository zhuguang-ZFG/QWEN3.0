"""Pack channel text replies with optional outbound media hints for the bridge."""

from __future__ import annotations

import os

from channel_gateway.models import InboundMessage
from channel_gateway.voice_reply import should_attach_voice_reply, voice_reply_max_chars


def invite_qr_enabled() -> bool:
    return os.environ.get("LIMA_CHANNEL_INVITE_QR", "1") == "1"


def pack_text_reply(
    text: str,
    msg: InboundMessage | None = None,
    *,
    send_invite_qr: bool = False,
    voice_pref_on: bool | None = None,
) -> dict:
    out: dict = {"text": text or ""}
    if send_invite_qr and invite_qr_enabled():
        out["send_invite_qr"] = True
    if msg is not None and should_attach_voice_reply(
        msg, text, user_pref_on=voice_pref_on
    ):
        plain = (text or "").strip()
        if plain:
            out["voice_reply_text"] = plain[: voice_reply_max_chars()]
    return out
