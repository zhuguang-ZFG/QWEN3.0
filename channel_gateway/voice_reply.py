"""WeChat outbound voice reply (MiMo TTS) policy."""

from __future__ import annotations

import os
import re

from channel_gateway.models import InboundMessage

_MAX = int(os.environ.get("LIMA_CHANNEL_VOICE_REPLY_MAX_CHARS", "480"))
_TTS_CAP = min(_MAX, int(os.environ.get("LIMA_CHANNEL_VOICE_TTS_SNIPPET_CHARS", "320")))


def voice_reply_globally_enabled() -> bool:
    return os.environ.get("LIMA_CHANNEL_VOICE_REPLY", "0") == "1"


def voice_reply_max_chars() -> int:
    return _MAX


def voice_reply_tts_text(msg: InboundMessage, text_out: str) -> str:
    """Text to synthesize for outbound voice; shorter when user sent voice."""
    snip = voice_reply_snippet(text_out)
    if not snip:
        return ""
    if not _inbound_was_voice(msg):
        return snip
    parts = re.split(r"[。！？\n]", snip)
    first = (parts[0] if parts else snip).strip() or snip
    cap = min(_TTS_CAP, 96)
    if len(first) > cap:
        first = first[:cap].rstrip()
    return first


def voice_reply_snippet(text: str, *, max_chars: int | None = None) -> str:
    """Short plain-text slice for TTS (drops footer, URLs, emoji)."""
    cap = _TTS_CAP if max_chars is None else min(max_chars, _MAX)
    t = (text or "").strip()
    for marker in ("——", "---", "___"):
        if marker in t:
            t = t.split(marker, 1)[0].strip()
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > cap:
        t = t[:cap].rstrip()
    return t


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
    snippet = voice_reply_snippet(text_out or "")
    if not snippet:
        return False
    if user_pref_on is True:
        return True
    return _inbound_was_voice(msg)
