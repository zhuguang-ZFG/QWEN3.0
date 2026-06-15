"""Channel Gateway service - dedupe, auth, command dispatch, response building.

Guests: scan/add-friend then chat (auto guest bind when enabled).
Owner-only commands (/code-task /device /status /artifact /memory) rejected for guests.
"""

from __future__ import annotations

import os

from channel_gateway.commands import is_owner_only, parse_command
from channel_gateway.greeting import greeting_reply, is_greeting
from channel_gateway.keyword_router import normalize_guest_text
from channel_gateway.media_inbound import extract_voice_transcript, resolve_media_to_text
from channel_gateway.models import BindingRole, BindingStatus, InboundMessage, OutboundReply
from channel_gateway.outbound import (
    ABOUT_TEXT,
    HELP_TEXT,
    OWNER_ONLY_HELP_HINT,
    TIP_FOOTER,
    WELCOME_GUEST,
    demo_text,
    finalize_outbound,
)
from channel_gateway.outbound_pack import pack_text_reply
from channel_gateway.invite import invite_text
from channel_gateway.service_dispatch import dispatch_command, dispatch_state_change, do_bind
from channel_gateway.store import ChannelStore

# Backward-compatible test import.
_TIP_FOOTER = TIP_FOOTER

_CMD_ALLOWED_WHEN_PAUSED = frozenset({"resume", "unbind", "help"})
_CMD_ALLOWED_WHEN_UNBOUND = frozenset({"bind", "help"})


def _auto_guest_bind_enabled() -> bool:
    return os.environ.get("LIMA_CHANNEL_AUTO_GUEST_BIND", "1") == "1"


class ChannelService:
    """Processes normalized inbound messages from a channel sidecar."""

    def __init__(
        self, store: ChannelStore, enabled: bool = True, *, wire_integrations: bool = False
    ):
        self._store = store
        self._enabled = enabled
        self._session = None
        self._chat_handler = lambda user, msg: f"[chat] {msg}"
        self._code_handler = lambda user, q: f"[code help] {q}"
        self._draw_handler = lambda user, prompt: f"[draw demo] {prompt}"
        self._demo_handler = lambda user: demo_text()
        self._about_handler = lambda user: ABOUT_TEXT
        self._reset_handler = lambda user: "[session cleared]"
        self._owner_code_task_handler = None
        self._owner_device_handler = None
        self._owner_status_handler = None
        self._owner_artifact_handler = None
        self._owner_memory_handler = None
        self._owner_digest_handler = None
        self._owner_github_handler = None
        self._voice_reply_prefs: dict[str, bool] = {}
        if wire_integrations:
            self._wire_integrations()

    def _pack_reply(
        self,
        text: str,
        msg: InboundMessage | None = None,
        *,
        send_invite_qr: bool = False,
    ) -> dict:
        pref = None
        if msg is not None:
            pref = self._voice_reply_prefs.get(msg.sender_id)
        return pack_text_reply(
            text,
            msg,
            send_invite_qr=send_invite_qr,
            voice_pref_on=pref,
        )

    def _ok_text(
        self,
        text: str,
        msg: InboundMessage | None = None,
        *,
        send_invite_qr: bool = False,
    ) -> OutboundReply:
        return OutboundReply(
            ok=True,
            reply=self._pack_reply(text, msg, send_invite_qr=send_invite_qr),
        )

    def _wire_integrations(self) -> None:
        from channel_gateway.chat_session import ChannelChatSession, session_enabled
        from channel_gateway.integrations import (
            build_chat_handler,
            build_code_handler,
            build_draw_handler,
            build_reset_handler,
        )

        if session_enabled():
            self._session = ChannelChatSession(self._store)
            self._chat_handler = build_chat_handler(session=self._session)
            self._code_handler = build_code_handler(session=self._session)
            self._reset_handler = build_reset_handler(self._session)
        else:
            self._chat_handler = build_chat_handler()
            self._code_handler = build_code_handler()
        self._draw_handler = build_draw_handler()

    def handle_message(self, msg: InboundMessage) -> OutboundReply:
        if not self._enabled:
            return OutboundReply(ok=False, error="WeChat bridge is disabled")

        raw_effective = resolve_media_to_text(msg.text, msg.attachments)
        if not raw_effective and msg.attachments:
            raw_effective = "[媒体消息]"
        msg.voice_transcript = extract_voice_transcript(raw_effective, msg.attachments)
        effective_text = normalize_guest_text(raw_effective)

        if not self._store.record_message(
            message_id=msg.message_id,
            channel="wechat",
            channel_user_id_raw=msg.sender_id,
            conversation_id_raw=msg.conversation_id,
            direction="inbound",
            intent="unknown",
            summary=effective_text[:200],
        ):
            return OutboundReply(ok=False, error="duplicate message")

        cmd = parse_command(effective_text)
        binding = self._store.get_binding_by_channel_user("wechat", msg.sender_id)

        if binding is None or binding.status == BindingStatus.REVOKED:
            if _auto_guest_bind_enabled() and cmd.intent != "bind":
                binding, created = self._store.ensure_guest_binding("wechat", msg.sender_id)
                if binding is None:
                    return OutboundReply(ok=False, error="Could not create guest binding")
                if created and cmd.intent == "chat" and is_greeting(effective_text):
                    return OutboundReply(ok=True, reply={"text": greeting_reply()})
                reply = dispatch_command(self, binding, msg, cmd)
                if created and reply.ok and reply.reply:
                    text = reply.reply.get("text", "")
                    if not text:
                        return reply
                    if cmd.intent in ("help", "demo"):
                        reply.reply["text"] = finalize_outbound(f"{WELCOME_GUEST}\n{text}")
                    elif cmd.intent == "chat":
                        reply.reply["text"] = finalize_outbound(f"{text}\n\n{TIP_FOOTER}")
                    else:
                        reply.reply["text"] = finalize_outbound(text)
                return reply
            return self._handle_unbound(msg, cmd)

        if binding.status == BindingStatus.PAUSED:
            return self._handle_paused(msg, cmd)

        if is_owner_only(cmd.intent) and binding.role != BindingRole.OWNER:
            return self._reject_owner_only(cmd)

        return dispatch_command(self, binding, msg, cmd)

    def _handle_unbound(self, msg: InboundMessage, cmd) -> OutboundReply:
        if cmd.intent == "bind":
            return do_bind(self, msg.sender_id, cmd.args)
        if cmd.intent == "help":
            return OutboundReply(ok=True, reply={"text": HELP_TEXT})
        return OutboundReply(
            ok=False,
            reply={"text": "请先发送 /bind <操作员码> 完成绑定，或联系管理员开通访客。"},
        )

    def _handle_paused(self, msg: InboundMessage, cmd) -> OutboundReply:
        if cmd.intent in _CMD_ALLOWED_WHEN_PAUSED:
            return dispatch_state_change(self, msg.sender_id, cmd)
        return OutboundReply(ok=False, reply={"text": "对话已暂停。发送 /resume 继续。"})

    def _reject_owner_only(self, cmd) -> OutboundReply:
        return OutboundReply(
            ok=False,
            reply={"text": f"/{cmd.intent} 仅主人可用。{OWNER_ONLY_HELP_HINT}"},
        )

    def _show_voice_transcript(self) -> bool:
        return os.environ.get("LIMA_CHANNEL_SHOW_VOICE_TRANSCRIPT", "1") == "1"

    def _prepend_voice_line(self, answer: str, voice_transcript: str) -> str:
        if not voice_transcript or not self._show_voice_transcript():
            return answer
        return f"🎤 识别：{voice_transcript}\n\n{answer}"

    def _do_chat(
        self,
        msg: InboundMessage,
        text: str,
        *,
        voice_transcript: str = "",
    ) -> OutboundReply:
        if not text.strip():
            return OutboundReply(ok=False, reply={"text": "请发送文字、语音、图片或文件，或 /help 查看命令。"})
        answer = self._chat_handler(msg.sender_id, text.strip())
        answer = self._prepend_voice_line(answer, voice_transcript)
        return self._ok_text(finalize_outbound(answer), msg)

    def _do_code(self, sender_id: str, question: str) -> OutboundReply:
        if not question.strip():
            return OutboundReply(ok=False, reply={"text": "用法：/code <编程问题>，例如 /code Python 列表推导式"})
        answer = self._code_handler(sender_id, question.strip())
        return OutboundReply(ok=True, reply={"text": finalize_outbound(answer)})

    def _do_draw(self, sender_id: str, prompt: str) -> OutboundReply:
        if not prompt.strip():
            return OutboundReply(ok=False, reply={"text": "用法：/draw <文字>，例如 /draw LiMa"})
        answer = self._draw_handler(sender_id, prompt.strip())
        return OutboundReply(ok=True, reply={"text": finalize_outbound(answer)})
