"""Channel Gateway LiMa integrations - guest-safe handlers.

V1: All handlers produce public/demo content only.
- Chat: routes through LiMa with guest persona, no private memory.
- Code: explanation/suggestion only, no task creation, no repo access.
- Draw: path preview metadata only, no Device Gateway queueing.
- Demo/About: static visitor-safe text.
- Reset: clears lightweight channel session only.
Owner-only handlers are in owner_handlers.py (re-exported below).
"""

from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from channel_gateway.chat_session import ChannelChatSession

# Re-export owner handlers for backward compatibility
from channel_gateway.owner_handlers import (  # noqa: F401
    build_owner_rejection_handler,
    build_owner_code_task_handler,
    build_owner_device_handler,
    build_owner_status_handler,
    build_owner_artifact_handler,
    build_owner_memory_handler,
    build_owner_digest_handler,
    build_owner_github_handler,
    _voice_task_from_channel_task,
    _queue_device_task_http,
)


def _friendly_guest_error(exc: BaseException) -> str:
    name = type(exc).__name__
    if name in ("TimeoutError", "ReadTimeout", "ConnectTimeout"):
        return "回复超时，请稍后再试或缩短问题。"
    if name in ("ConnectionError", "ConnectError", "RemoteDisconnected"):
        return "暂时连不上模型服务，请稍后再试。"
    if name in ("HTTPError", "ClientError"):
        return "上游服务异常，请稍后再试。"
    return "暂时无法回答，请稍后再试。"


def build_chat_handler(
    route_fn: Optional[Callable] = None,
    call_api_fn: Optional[Callable] = None,
    session: Optional["ChannelChatSession"] = None,
) -> Callable[[str, str], str]:
    """Guest chat handler: routes through LiMa with public persona."""

    if route_fn is None:
        import routing_engine
        import http_caller

        def _default_route(query, messages, call_fn):
            return routing_engine.route(
                query, messages, call_fn=call_fn, channel_role="guest")

        route_fn = _default_route
        call_api_fn = http_caller.call_api

    def handler(user_id: str, text: str) -> str:
        if not text.strip():
            return ""
        try:
            system_prompt = (
                "你是 LiMa，深圳市动力巢科技有限公司的智能助手，正在通过微信服务访客。"
                "用简体中文，简洁、实用、友好。"
                "不要自称 Hermes；不要透露服务器路径、API 密钥、内部架构。"
                "若被问公司/产品：动力巢科技，官网 www.donglilicao.com，在线体验 chat.donglicao.com。"
                "若被问模型：由 LiMa 智能路由多后端作答，聚焦解决用户问题。"
            )
            messages = [{"role": "system", "content": system_prompt}]
            if session is not None:
                messages.extend(session.get_messages(user_id))
            messages.append({"role": "user", "content": text})
            if call_api_fn:
                result = route_fn(text, messages, call_fn=call_api_fn)
            else:
                result = route_fn(text, messages)
            answer = getattr(result, "answer", "") if hasattr(result, "answer") else str(result)
            reply = answer if answer else "暂时没有生成内容，请换个问法或稍后再试。"
            if session is not None:
                session.record_turn(user_id, "user", text)
                session.record_turn(user_id, "assistant", reply)
            return reply
        except Exception as e:
            return _friendly_guest_error(e)

    return handler


def build_reset_handler(session: "ChannelChatSession") -> Callable[[str], str]:
    def handler(user_id: str) -> str:
        session.clear(user_id)
        return "已清空本会话上下文（最近对话记录）。"
    return handler


def build_code_handler(
    route_fn: Optional[Callable] = None,
    session: Optional["ChannelChatSession"] = None,
) -> Callable[[str, str], str]:
    """Guest code handler: explanation/suggestion only. No task creation, no repo reads."""

    if route_fn is None:
        import routing_engine
        import http_caller

        def _default_route(query, messages, call_fn):
            return routing_engine.route(
                query, messages, call_fn=call_fn, channel_role="guest")

        route_fn = _default_route
        call_api_fn = http_caller.call_api
    else:
        call_api_fn = None

    def handler(user_id: str, question: str) -> str:
        try:
            system_prompt = (
                "你是 LiMa 编程助手，访客在微信上提问。"
                "用简体中文讲解，必要时给简短示例。"
                "只读说明：不创建文件、不执行命令、不访问仓库。"
            )
            messages = [{"role": "system", "content": system_prompt}]
            if session is not None:
                messages.extend(session.get_messages(user_id))
            messages.append({"role": "user", "content": question})
            if call_api_fn:
                result = route_fn(question, messages, call_fn=call_api_fn)
            else:
                result = route_fn(question, messages)
            answer = getattr(result, "answer", "") if hasattr(result, "answer") else str(result)
            reply = answer if answer else "暂时无法解答该问题，请换个说法。"
            if session is not None:
                session.record_turn(user_id, "user", f"/code {question}")
                session.record_turn(user_id, "assistant", reply)
            return reply
        except Exception as e:
            return _friendly_guest_error(e)

    return handler


def build_draw_handler() -> Callable[[str, str], str]:
    """Guest draw handler: preview/demo metadata only. No Device Gateway queueing."""

    def handler(user_id: str, prompt: str) -> str:
        safe_text = prompt.strip()[:200]
        if not safe_text:
            return "用法：/draw <文字>，例如 /draw LiMa"
        try:
            from device_gateway.path_pipeline import render_text_task

            rendered = render_text_task(safe_text)
            path = rendered.get("path") or []
            preview = str(rendered.get("preview_svg", ""))
            lines = [
                f"绘图预览：「{safe_text}」",
                "",
                "（仅 demo，不会下发到真实设备）",
                f"  路径点数：{rendered.get('point_count', len(path))}",
                "  字体：描边 demo",
            ]
            if preview:
                lines.append(f"  SVG 摘要：{preview[:120]}{'...' if len(preview) > 120 else ''}")
            lines.extend([
                "",
                "真实设备绘制需主人账号（/bind 操作员码）。",
            ])
            return "\n".join(lines)
        except ImportError:
            return (
                f"绘图预览：「{safe_text}」\n\n"
                "预览模块未加载。\n"
                "真实设备绘制需主人账号。"
            )

    return handler
