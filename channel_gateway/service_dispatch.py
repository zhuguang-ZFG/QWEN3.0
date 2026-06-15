"""Command dispatch helpers for ChannelService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from channel_gateway.branding import company_pitch
from channel_gateway.channel_tools import CHANNEL_TOOL_INTENTS, run_channel_tool, tools_help_suffix
from channel_gateway.invite import invite_text
from channel_gateway.models import BindingRole, BindingStatus, OutboundReply
from channel_gateway.outbound import (
    ABOUT_TEXT,
    FILE_HELP,
    HELP_TEXT,
    VOICE_HELP,
    demo_text,
    finalize_outbound,
)
from channel_gateway.voice_reply import parse_voice_reply_command, voice_reply_globally_enabled

if TYPE_CHECKING:
    from channel_gateway.service import ChannelService


def dispatch_state_change(svc: ChannelService, sender_id: str, cmd: Any) -> OutboundReply:
    binding = svc._store.get_binding_by_channel_user("wechat", sender_id)
    if binding is None:
        return OutboundReply(ok=False, error="No binding found")

    if cmd.intent == "pause":
        svc._store.set_binding_status(binding.binding_id, BindingStatus.PAUSED)
        return OutboundReply(ok=True, reply={"text": "已暂停。发送 /resume 继续对话。"})

    if cmd.intent == "resume":
        svc._store.set_binding_status(binding.binding_id, BindingStatus.ACTIVE)
        return OutboundReply(ok=True, reply={"text": "已恢复，可以继续聊天。"})

    if cmd.intent == "unbind":
        svc._store.set_binding_status(binding.binding_id, BindingStatus.REVOKED)
        return OutboundReply(
            ok=True,
            reply={"text": "已解除绑定。直接发消息可再次自动开通访客能力。"},
        )

    return OutboundReply(ok=False, error=f"Unknown state change: {cmd.intent}")


def do_bind(svc: ChannelService, sender_id: str, code: str) -> OutboundReply:
    if not code or not code.strip():
        return OutboundReply(ok=False, reply={"text": "用法：/bind <操作员码>（向 LiMa 管理员索取）。"})
    code = code.strip()
    if not svc._store.validate_binding_code(code):
        return OutboundReply(ok=False, reply={"text": "绑定码无效或已过期，请重新索取。"})

    binding_id = f"bind_{sender_id[:20]}_{code[:6]}"
    ok = svc._store.create_binding(
        binding_id=binding_id,
        channel="wechat",
        channel_user_id_raw=sender_id,
        display_name=sender_id[:20],
        lima_user_id="operator",
    )
    if not ok:
        return OutboundReply(ok=False, reply={"text": "绑定失败，可能已绑定过该账号。"})

    binding = svc._store.get_binding_by_channel_user("wechat", sender_id)
    role = binding.role if binding else BindingRole.GUEST
    role_zh = "主人" if role == BindingRole.OWNER else "访客"
    welcome = f"已绑定为 {role_zh}。欢迎使用 LiMa！\n\n{HELP_TEXT}{tools_help_suffix()}"
    return OutboundReply(ok=True, reply={"text": welcome})


def _owner_handler(svc: ChannelService, attr: str, builder_name: str):
    handler = getattr(svc, attr)
    if handler is None:
        from channel_gateway import integrations

        handler = getattr(integrations, builder_name)()
        setattr(svc, attr, handler)
    return handler


def dispatch_command(svc: ChannelService, binding, msg, cmd) -> OutboundReply:
    intent = cmd.intent

    if intent in ("pause", "resume", "unbind"):
        return dispatch_state_change(svc, msg.sender_id, cmd)

    if intent == "chat":
        return svc._do_chat(msg, cmd.args, voice_transcript=msg.voice_transcript)

    if intent == "code":
        return svc._do_code(msg.sender_id, cmd.args)

    if intent == "draw":
        return svc._do_draw(msg.sender_id, cmd.args)

    if intent == "demo":
        return OutboundReply(ok=True, reply={"text": finalize_outbound(svc._demo_handler(msg.sender_id))})

    if intent == "about":
        return OutboundReply(ok=True, reply={"text": finalize_outbound(svc._about_handler(msg.sender_id))})

    if intent == "reset":
        return OutboundReply(ok=True, reply={"text": finalize_outbound(svc._reset_handler(msg.sender_id))})

    if intent == "help":
        return OutboundReply(ok=True, reply={"text": finalize_outbound(HELP_TEXT + tools_help_suffix())})

    if intent == "company":
        return OutboundReply(ok=True, reply={"text": finalize_outbound(company_pitch())})

    if intent == "invite":
        return svc._ok_text(finalize_outbound(invite_text()), msg, send_invite_qr=False)

    if intent == "voice_reply":
        toggle = parse_voice_reply_command(cmd.raw_text)
        if toggle is None:
            toggle = "on" if (cmd.args or "").strip().lower() in ("on", "开", "") else "off"
        if not voice_reply_globally_enabled():
            return svc._ok_text("语音回复未在服务器开启（需 LIMA_CHANNEL_VOICE_REPLY=1）。", msg)
        svc._voice_reply_prefs[msg.sender_id] = toggle == "on"
        state = "已开启" if toggle == "on" else "已关闭"
        hint = (
            f"{state}：您发语音后，回复会尽量附带语音条。"
            if toggle == "on"
            else f"{state}：仅文字回复（发语音也不会附带语音条）。"
        )
        return svc._ok_text(finalize_outbound(hint), msg)

    if intent == "voice_help":
        return svc._ok_text(finalize_outbound(VOICE_HELP), msg)

    if intent == "file_help":
        return svc._ok_text(finalize_outbound(FILE_HELP), msg)

    if intent in CHANNEL_TOOL_INTENTS:
        text = run_channel_tool(
            svc._store,
            intent,
            cmd.args,
            channel_user_id_raw=msg.sender_id,
            role=binding.role,
        )
        return svc._ok_text(finalize_outbound(text), msg)

    owner_routes = {
        "code_task": ("_owner_code_task_handler", "build_owner_code_task_handler", lambda h: h(msg.sender_id, cmd.args)),
        "device": ("_owner_device_handler", "build_owner_device_handler", lambda h: h(msg.sender_id, cmd.args)),
        "status": ("_owner_status_handler", "build_owner_status_handler", lambda h: h(msg.sender_id)),
        "artifact": ("_owner_artifact_handler", "build_owner_artifact_handler", lambda h: h(cmd.args)),
        "memory": ("_owner_memory_handler", "build_owner_memory_handler", lambda h: h(msg.sender_id, cmd.args)),
        "digest": ("_owner_digest_handler", "build_owner_digest_handler", lambda h: h(msg.sender_id)),
        "github": ("_owner_github_handler", "build_owner_github_handler", lambda h: h(msg.sender_id, cmd.args)),
    }
    if intent in owner_routes:
        attr, builder, call = owner_routes[intent]
        handler = _owner_handler(svc, attr, builder)
        return OutboundReply(ok=True, reply={"text": call(handler)})

    if intent == "unknown":
        return OutboundReply(
            ok=False,
            reply={"text": "未识别的命令。发送 /help 查看帮助，/menu 查看实用工具。"},
        )

    return OutboundReply(ok=False, error=f"Unhandled intent: {intent}")
