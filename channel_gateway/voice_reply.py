"""WeChat outbound voice reply (MiMo TTS) policy."""

from __future__ import annotations

import os
import re

from channel_gateway.models import InboundMessage

_MAX = int(os.environ.get("LIMA_CHANNEL_VOICE_REPLY_MAX_CHARS", "480"))


def voice_reply_globally_enabled() -> bool:
    return os.environ.get("LIMA_CHANNEL_VOICE_REPLY", "0") == "1"


def voice_reply_max_chars() -> int:
    return _MAX


def parse_voice_reply_command(text: str) -> str | None:
    """Return 'on', 'off', or None if not a voice-reply toggle command."""
    raw = (text or "").strip()
    m = re.match(r"^/?语音回复(?:\s+(on|off|开|关|开启|关闭))?$", raw, re.I)
    if not m:
        return None
    arg = (m.group(1) or "on").strip().lower()
    if arg in ("off", "关", "关闭"):
        return "off"
    return "on"


def _inbound_was_voice(msg: InboundMessage) -> bool:
    if (msg.voice_transcript or "").strip():
        return True
    for att in msg.attachments or []:
        if att.get("kind") == "voice":
            return True
    return False


def should_attach_voice_reply(
    msg: InboundMessage,
    text_out: str,
    *,
    user_pref_on: bool | None = None,
) -> bool:
    if not voice_reply_globally_enabled():
        return False
    if user_pref_on is False:
        return False
    body = (text_out or "").strip()
    if not body or len(body) > _MAX:
        return False
    if user_pref_on is True:
        return True
    return _inbound_was_voice(msg)
