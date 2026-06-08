"""Channel Gateway service - dedupe, auth, command dispatch, response building.

Guests: scan/add-friend then chat (auto guest bind when enabled).
Owner-only commands (/code-task /device /status /artifact /memory) rejected for guests.
"""

import logging
import os

from channel_gateway.branding import company_pitch, maybe_brand_footer
from channel_gateway.channel_tools import (
    CHANNEL_TOOL_INTENTS,
    run_channel_tool,
    tools_help_suffix,
)
from channel_gateway.commands import is_owner_only, parse_command
from channel_gateway.constants import (
    ABOUT_TEXT,
    CMD_ALLOWED_WHEN_PAUSED,
    CMD_ALLOWED_WHEN_UNBOUND,
    FILE_HELP,
    HELP_TEXT,
    OWNER_ONLY_HELP_HINT,
    TIP_FOOTER,
    VOICE_HELP,
    WELCOME_GUEST,
)
from channel_gateway.helpers import (
    auto_guest_bind_enabled,
    demo_text,
    finalize_outbound,
    greeting_reply,
    is_greeting,
)
from channel_gateway.invite import invite_text
from channel_gateway.keyword_router import normalize_guest_text
from channel_gateway.media_inbound import extract_voice_transcript, resolve_media_to_text
from channel_gateway.models import (
    BindingRole,
    BindingStatus,
    InboundMessage,
    OutboundReply,
)
from channel_gateway.outbound_pack import pack_text_reply
from channel_gateway.store import ChannelStore
from channel_gateway.voice_reply import parse_voice_reply_command, voice_reply_globally_enabled

_log = logging.getLogger(__name__)


class ChannelService:
    """Processes normalized inbound messages from a channel sidecar."""

    def __init__(
        self, store: ChannelStore, enabled: bool = True, *, wire_integrations: bool = False
    ):
        self._store = store
        self._enabled = enabled
        self._session = None
        # Guest-safe handlers injected for testing
        self._chat_handler = lambda user, msg: f"[chat] {msg}"
        self._code_handler = lambda user, q: f"[code help] {q}"
        self._draw_handler = lambda user, prompt: f"[draw demo] {prompt}"
        self._demo_handler = lambda user: demo_text()
        self._about_handler = lambda user: ABOUT_TEXT
        self._reset_handler = lambda user: "[session cleared]"
        # Owner-only handlers — lazily built on first access
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

    # -- Main Entry ----------------------------------------------------------

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

        # Auth: unbound / revoked → auto guest bind (zero-friction)
        if binding is None or binding.status == BindingStatus.REVOKED:
            if auto_guest_bind_enabled() and cmd.intent != "bind":
                binding, created = self._store.ensure_guest_binding(
                    "wechat", msg.sender_id
                )
                if binding is None:
                    return OutboundReply(ok=False, error="Could not create guest binding")
                if created and cmd.intent == "chat" and is_greeting(effective_text):
                    return OutboundReply(ok=True, reply={"text": greeting_reply()})
                reply = self._dispatch(binding, msg, cmd)
                if created and reply.ok and reply.reply:
                    text = reply.reply.get("text", "")
                    if not text:
                        return reply
                    if cmd.intent in ("help", "demo"):
                        reply.reply["text"] = finalize_outbound(
                            f"{WELCOME_GUEST}\n{text}"
                        )
                    elif cmd.intent == "chat":
                        reply.reply["text"] = finalize_outbound(
                            f"{text}\n\n{TIP_FOOTER}"
                        )
                    else:
                        reply.reply["text"] = finalize_outbound(text)
                return reply
            return self._handle_unbound(msg, cmd)

        # Auth: paused
        if binding.status == BindingStatus.PAUSED:
            return self._handle_paused(msg, cmd)

        # Owner-only command rejection for guests
        if is_owner_only(cmd.intent) and binding.role != BindingRole.OWNER:
            return self._reject_owner_only(cmd)

        return self._dispatch(binding, msg, cmd)

    # -- Auth States ---------------------------------------------------------

    def _handle_unbound(self, msg: InboundMessage, cmd) -> OutboundReply:
        if cmd.intent == "bind":
            return self._do_bind(msg.sender_id, cmd.args)
        if cmd.intent == "help":
            return OutboundReply(ok=True, reply={"text": HELP_TEXT})
        return OutboundReply(
            ok=False,
            reply={"text": "请先发送 /bind <操作员码> 完成绑定，或联系管理员开通访客。"},
        )

    def _handle_paused(self, msg: InboundMessage, cmd) -> OutboundReply:
        if cmd.intent in CMD_ALLOWED_WHEN_PAUSED:
            return self._dispatch_state_change(msg.sender_id, cmd)
        return OutboundReply(
            ok=False,
            reply={"text": "对话已暂停。发送 /resume 继续。"},
        )

    def _reject_owner_only(self, cmd) -> OutboundReply:
        return OutboundReply(
            ok=False,
            reply={"text": f"/{cmd.intent} 仅主人可用。{OWNER_ONLY_HELP_HINT}"},
        )

    # -- Dispatch ------------------------------------------------------------

    def _dispatch(self, binding, msg: InboundMessage, cmd) -> OutboundReply:
        intent = cmd.intent

        if intent in ("pause", "resume", "unbind"):
            return self._dispatch_state_change(msg.sender_id, cmd)

        if intent == "chat":
            return self._do_chat(
                msg,
                cmd.args,
                voice_transcript=msg.voice_transcript,
            )

        if intent == "code":
            return self._do_code(msg.sender_id, cmd.args)

        if intent == "draw":
            return self._do_draw(msg.sender_id, cmd.args)

        if intent == "demo":
            return OutboundReply(
                ok=True,
                reply={"text": finalize_outbound(self._demo_handler(msg.sender_id))},
            )

        if intent == "about":
            return OutboundReply(
                ok=True,
                reply={"text": finalize_outbound(self._about_handler(msg.sender_id))},
            )

        if intent == "reset":
            result = self._reset_handler(msg.sender_id)
            return OutboundReply(ok=True, reply={"text": result})

        if intent == "help":
            return OutboundReply(ok=True, reply={"text": HELP_TEXT + tools_help_suffix()})

        if intent == "company":
            return OutboundReply(ok=True, reply={"text": company_pitch()})

        if intent == "invite":
            return self._ok_text(invite_text(), msg, send_invite_qr=True)

        if intent == "voice_help":
            return OutboundReply(ok=True, reply={"text": VOICE_HELP})

        if intent == "file_help":
            return OutboundReply(ok=True, reply={"text": FILE_HELP})

        if intent == "voice_reply":
            result, pref_on = parse_voice_reply_command(cmd.args)
            if result and pref_on is not None:
                self._voice_reply_prefs[msg.sender_id] = pref_on
            return OutboundReply(ok=True, reply={"text": result})

        if intent in CHANNEL_TOOL_INTENTS:
            result = run_channel_tool(
                self._store,
                intent,
                cmd.args,
                channel_user_id_raw=msg.sender_id,
                role=binding.role,
            )
            return self._ok_text(finalize_outbound(result), msg)

        # Owner-only commands (lazily wired)
        if intent == "code_task":
            if self._owner_code_task_handler is None:
                from channel_gateway.integrations import build_owner_code_task_handler
                self._owner_code_task_handler = build_owner_code_task_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_code_task_handler(msg.sender_id, cmd.args)},
            )

        if intent == "device":
            if self._owner_device_handler is None:
                from channel_gateway.integrations import build_owner_device_handler
                self._owner_device_handler = build_owner_device_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_device_handler(msg.sender_id, cmd.args)},
            )

        if intent == "status":
            if self._owner_status_handler is None:
                from channel_gateway.integrations import build_owner_status_handler
                self._owner_status_handler = build_owner_status_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_status_handler(msg.sender_id)},
            )

        if intent == "artifact":
            if self._owner_artifact_handler is None:
                from channel_gateway.integrations import build_owner_artifact_handler
                self._owner_artifact_handler = build_owner_artifact_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_artifact_handler(cmd.args)},
            )

        if intent == "memory":
            if self._owner_memory_handler is None:
                from channel_gateway.integrations import build_owner_memory_handler
                self._owner_memory_handler = build_owner_memory_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_memory_handler(msg.sender_id, cmd.args)},
            )

        if intent == "digest":
            if self._owner_digest_handler is None:
                from channel_gateway.integrations import build_owner_digest_handler
                self._owner_digest_handler = build_owner_digest_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_digest_handler(msg.sender_id)},
            )

        if intent == "github":
            if self._owner_github_handler is None:
                from channel_gateway.integrations import build_owner_github_handler
                self._owner_github_handler = build_owner_github_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_github_handler(msg.sender_id, cmd.args)},
            )

        return OutboundReply(ok=False, error=f"Unhandled intent: {intent}")

    # -- State Change --------------------------------------------------------

    def _dispatch_state_change(self, sender_id: str, cmd) -> OutboundReply:
        binding = self._store.get_binding_by_channel_user("wechat", sender_id)
        if binding is None:
            return OutboundReply(ok=False, error="No binding found")

        if cmd.intent == "pause":
            self._store.set_binding_status(binding.binding_id, BindingStatus.PAUSED)
            return OutboundReply(ok=True, reply={"text": "已暂停。发送 /resume 继续对话。"})

        if cmd.intent == "resume":
            self._store.set_binding_status(binding.binding_id, BindingStatus.ACTIVE)
            return OutboundReply(ok=True, reply={"text": "已恢复，可以继续聊天。"})

        if cmd.intent == "unbind":
            self._store.set_binding_status(binding.binding_id, BindingStatus.REVOKED)
            return OutboundReply(
                ok=True,
                reply={"text": "已解除绑定。直接发消息可再次自动开通访客能力。"},
            )

        return OutboundReply(ok=False, error=f"Unknown state change: {cmd.intent}")

    # -- Command Handlers ----------------------------------------------------

    def _do_bind(self, sender_id: str, code: str) -> OutboundReply:
        if not code or not code.strip():
            return OutboundReply(
                ok=False,
                reply={"text": "用法：/bind <操作员码>（向 LiMa 管理员索取）。"},
            )
        code = code.strip()
        if not self._store.validate_binding_code(code):
            return OutboundReply(
                ok=False, reply={"text": "绑定码无效或已过期，请重新索取。"}
            )

        binding_id = f"bind_{sender_id[:20]}_{code[:6]}"
        ok = self._store.create_binding(
            binding_id=binding_id,
            channel="wechat",
            channel_user_id_raw=sender_id,
            display_name=sender_id[:20],
            lima_user_id="operator",
        )
        if not ok:
            return OutboundReply(
                ok=False, reply={"text": "绑定失败，可能已绑定过该账号。"}
            )

        binding = self._store.get_binding_by_channel_user("wechat", sender_id)
        role = binding.role if binding else BindingRole.GUEST
        role_zh = "主人" if role == BindingRole.OWNER else "访客"
        welcome = f"已绑定为 {role_zh}。欢迎使用 LiMa！\n\n{HELP_TEXT}{tools_help_suffix()}"
        return OutboundReply(ok=True, reply={"text": welcome})

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
            return OutboundReply(
                ok=False,
                reply={"text": "请发送文字、语音、图片或文件，或 /help 查看命令。"},
            )
        answer = self._chat_handler(msg.sender_id, text.strip())
        answer = self._prepend_voice_line(answer, voice_transcript)
        return self._ok_text(finalize_outbound(answer), msg)

    def _do_code(self, sender_id: str, question: str) -> OutboundReply:
        if not question.strip():
            return OutboundReply(
                ok=False,
                reply={"text": "用法：/code <编程问题>，例如 /code Python 列表推导式"},
            )
        answer = self._code_handler(sender_id, question.strip())
        return OutboundReply(ok=True, reply={"text": finalize_outbound(answer)})

    def _do_draw(self, sender_id: str, prompt: str) -> OutboundReply:
        if not prompt.strip():
            return OutboundReply(
                ok=False,
                reply={"text": "用法：/draw <文字>，例如 /draw LiMa"},
            )
        answer = self._draw_handler(sender_id, prompt.strip())
        return OutboundReply(ok=True, reply={"text": finalize_outbound(answer)})
