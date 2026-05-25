"""Channel Gateway service - dedupe, auth, command dispatch, response building.

Guests: scan/add-friend then chat (auto guest bind when enabled).
Owner-only commands (/code-task /device /status /artifact /memory) rejected for guests.
"""

import os
import re

from channel_gateway.commands import parse_command, is_owner_only
from channel_gateway.keyword_router import normalize_guest_text
from channel_gateway.media_inbound import extract_voice_transcript, resolve_media_to_text
from channel_gateway.models import (
    BindingRole,
    BindingStatus,
    InboundMessage,
    OutboundReply,
)
from channel_gateway.channel_tools import (
    CHANNEL_TOOL_INTENTS,
    run_channel_tool,
    tools_help_suffix,
)
from channel_gateway.branding import company_pitch, maybe_brand_footer
from channel_gateway.invite import invite_text
from channel_gateway.outbound_pack import pack_text_reply
from channel_gateway.voice_reply import parse_voice_reply_command, voice_reply_globally_enabled
from channel_gateway.store import ChannelStore

_CMD_ALLOWED_WHEN_PAUSED = frozenset({"resume", "unbind", "help"})
_CMD_ALLOWED_WHEN_UNBOUND = frozenset({"bind", "help"})

def _auto_guest_bind_enabled() -> bool:
    return os.environ.get("LIMA_CHANNEL_AUTO_GUEST_BIND", "1") == "1"

_WELCOME_GUEST = (
    "欢迎使用 LiMa 微信助手（动力巢科技）！加好友即可用，无需绑定码。\n"
    "支持：文字聊天 · 语音消息 · 图片/文件分析 · /menu 实用工具。\n"
    "发 /公司 了解我们，/help 看全部命令。\n"
)

_TIP_FOOTER = "提示：发「菜单」「官网」「帮助」也行 · /reset 清空对话"

_OWNER_ONLY_HELP_HINT = (
    "该命令仅主人可用（需 /bind 操作员码）。"
    "访客可用：聊天、/code、/draw、/menu 工具等。"
)

_HELP_TEXT = (
    "LiMa 微信助手（动力巢科技）\n"
    "——\n"
    "直接发文字即可聊天（会记住最近几轮）。\n"
    "发语音条 → 自动转写后回答；发图片/文件 → 自动分析摘要。\n"
    "/help — 本帮助\n"
    "/menu — 联网工具（天气、百科、算式等）\n"
    "/公司 — 动力巢科技与 LiMa 介绍\n"
    "/邀请 — 如何把机器人推荐给朋友（扫码添加）\n"
    "/语音 — 语音使用说明\n"
    "/语音回复 on|off — 是否附带语音条回复（需 LIMA_CHANNEL_VOICE_REPLY=1）\n"
    "/文件 — 文件分析说明\n"
    "/demo — 推荐体验顺序\n"
    "/about — 关于 LiMa\n"
    "/code <问题> — 代码讲解\n"
    "/draw <文字> — 路径绘制预览\n"
    "/reset — 清空会话\n"
    "/pause · /resume · /unbind · /bind <码>\n"
    "主人：/简报 /github /code-task /device /status /memory"
)

_VOICE_HELP = (
    "【语音交互】\n"
    "直接发送微信语音条即可。\n"
    "· 若微信已带转写文字，会优先使用\n"
    "· 否则使用小米 MiMo 语音模型转写（与 TTS 共用 MIMO_TTS_KEY）\n"
    "· 备用：Groq / SiliconFlow Whisper\n"
    "· 识别后按普通聊天回答，/reset 可清空上下文"
)

_FILE_HELP = (
    "【文件 / 图片分析】\n"
    "· 图片：发送照片，可附带文字说明你的问题\n"
    "· 文件：支持 .txt .md .py .json .csv .pdf 等（单文件约 1.5MB 内）\n"
    "· 其他格式请截图或粘贴关键文字\n"
    "分析结果由 LiMa 多后端路由生成，仅供访客演示与办公辅助。"
)

_ABOUT_TEXT = (
    "LiMa 是动力巢科技旗下的个人编码与硬件助手。\n"
    "微信入口：文字/语音/图片/文件分析 + /menu 实用工具。\n"
    "完整能力（代码任务、设备、记忆）请用 LiMa IDE 或 chat.donglicao.com。\n"
    "我是 LiMa，不是 Hermes。发 /公司 查看公司与产品简介。"
)

_GREETING_RE = re.compile(
    r"^(你好|您好|嗨|哈喽|在吗|有人吗|hi|hello|hey)[\s!！?？。.~、，,]*$",
    re.IGNORECASE,
)


def _is_greeting(text: str) -> bool:
    return bool(_GREETING_RE.match((text or "").strip()))


def _greeting_reply() -> str:
    return maybe_brand_footer(
        "你好，我是 LiMa 微信助手（动力巢科技）。\n"
        "可打字、发语音、发图片/文件；发「菜单」或用 /menu。\n"
        "发「官网」或 /公司 了解我们，「帮助」或 /help 看命令。"
    )


def _finalize_outbound(text: str) -> str:
    return maybe_brand_footer(text or "")


def _demo_text() -> str:
    lines = [
        "LiMa 体验路线：",
        "1. 直接问一个问题（例如：Python 里 async 是什么）",
        "2. /算 123*456 — 计算器",
        "3. /百科 Python — 维基摘要",
        "4. /code 用列表推导式过滤空字符串",
        "5. /draw LiMa — 路径预览",
        "6. /menu — 全部联网工具",
        "7. /reset — 清空对话记忆",
        "主人：/简报 · /github owner/repo path",
    ]
    try:
        from channel_gateway.chat_session import max_turns, session_enabled

        if session_enabled():
            lines[1] = f"1. 直接发消息（保留最近 {max_turns()} 轮）"
    except ImportError:
        pass
    return "\n".join(lines)


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
        self._demo_handler = lambda user: _demo_text()
        self._about_handler = lambda user: _ABOUT_TEXT
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
            if _auto_guest_bind_enabled() and cmd.intent != "bind":
                binding, created = self._store.ensure_guest_binding(
                    "wechat", msg.sender_id
                )
                if binding is None:
                    return OutboundReply(ok=False, error="Could not create guest binding")
                if created and cmd.intent == "chat" and _is_greeting(effective_text):
                    return OutboundReply(ok=True, reply={"text": _greeting_reply()})
                reply = self._dispatch(binding, msg, cmd)
                if created and reply.ok and reply.reply:
                    text = reply.reply.get("text", "")
                    if not text:
                        return reply
                    if cmd.intent in ("help", "demo"):
                        reply.reply["text"] = _finalize_outbound(
                            f"{_WELCOME_GUEST}\n{text}"
                        )
                    elif cmd.intent == "chat":
                        reply.reply["text"] = _finalize_outbound(
                            f"{text}\n\n{_TIP_FOOTER}"
                        )
                    else:
                        reply.reply["text"] = _finalize_outbound(text)
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
            return OutboundReply(ok=True, reply={"text": _HELP_TEXT})
        return OutboundReply(
            ok=False,
            reply={"text": "请先发送 /bind <操作员码> 完成绑定，或联系管理员开通访客。"},
        )

    def _handle_paused(self, msg: InboundMessage, cmd) -> OutboundReply:
        if cmd.intent in _CMD_ALLOWED_WHEN_PAUSED:
            return self._dispatch_state_change(msg.sender_id, cmd)
        return OutboundReply(
            ok=False,
            reply={"text": "对话已暂停。发送 /resume 继续。"},
        )

    def _reject_owner_only(self, cmd) -> OutboundReply:
        return OutboundReply(
            ok=False,
            reply={"text": f"/{cmd.intent} 仅主人可用。{_OWNER_ONLY_HELP_HINT}"},
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
                reply={"text": _finalize_outbound(self._demo_handler(msg.sender_id))},
            )

        if intent == "about":
            return OutboundReply(
                ok=True,
                reply={"text": _finalize_outbound(self._about_handler(msg.sender_id))},
            )

        if intent == "reset":
            return OutboundReply(
                ok=True,
                reply={"text": _finalize_outbound(self._reset_handler(msg.sender_id))},
            )

        if intent == "help":
            return OutboundReply(
                ok=True,
                reply={"text": _finalize_outbound(_HELP_TEXT + tools_help_suffix())},
            )

        if intent == "company":
            return OutboundReply(
                ok=True, reply={"text": _finalize_outbound(company_pitch())},
            )

        if intent == "invite":
            return self._ok_text(
                _finalize_outbound(invite_text()),
                msg,
                send_invite_qr=False,
            )

        if intent == "voice_reply":
            toggle = parse_voice_reply_command(cmd.raw_text)
            if toggle is None:
                toggle = "on" if (cmd.args or "").strip().lower() in ("on", "开", "") else "off"
            if not voice_reply_globally_enabled():
                return self._ok_text(
                    "语音回复未在服务器开启（需 LIMA_CHANNEL_VOICE_REPLY=1）。",
                    msg,
                )
            self._voice_reply_prefs[msg.sender_id] = toggle == "on"
            state = "已开启" if toggle == "on" else "已关闭"
            hint = (
                f"{state}：您发语音后，回复会尽量附带语音条。"
                if toggle == "on"
                else f"{state}：仅文字回复（发语音也不会附带语音条）。"
            )
            return self._ok_text(_finalize_outbound(hint), msg)

        if intent == "voice_help":
            return self._ok_text(_finalize_outbound(_VOICE_HELP), msg)

        if intent == "file_help":
            return self._ok_text(_finalize_outbound(_FILE_HELP), msg)

        if intent in CHANNEL_TOOL_INTENTS:
            text = run_channel_tool(
                self._store,
                intent,
                cmd.args,
                channel_user_id_raw=msg.sender_id,
                role=binding.role,
            )
            return self._ok_text(_finalize_outbound(text), msg)

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

        if intent == "unknown":
            return OutboundReply(
                ok=False,
                reply={
                    "text": (
                        "未识别的命令。发送 /help 查看帮助，/menu 查看实用工具。"
                    )
                },
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
        welcome = f"已绑定为 {role_zh}。欢迎使用 LiMa！\n\n{_HELP_TEXT}{tools_help_suffix()}"
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
        return self._ok_text(_finalize_outbound(answer), msg)

    def _do_code(self, sender_id: str, question: str) -> OutboundReply:
        if not question.strip():
            return OutboundReply(
                ok=False,
                reply={"text": "用法：/code <编程问题>，例如 /code Python 列表推导式"},
            )
        answer = self._code_handler(sender_id, question.strip())
        return OutboundReply(ok=True, reply={"text": _finalize_outbound(answer)})

    def _do_draw(self, sender_id: str, prompt: str) -> OutboundReply:
        if not prompt.strip():
            return OutboundReply(
                ok=False,
                reply={"text": "用法：/draw <文字>，例如 /draw LiMa"},
            )
        answer = self._draw_handler(sender_id, prompt.strip())
        return OutboundReply(ok=True, reply={"text": _finalize_outbound(answer)})
