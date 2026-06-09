"""
Anthropic messages handler - Simplified stub for strategic pivot.

原 anthropic_messages_handler.py 已删除（编码助手专属）。
此文件提供最小占位符，避免大量修改 routes/chat_endpoints.py。
Phase 2 将重构为设备场景专用的消息处理。
"""
from typing import Any
from fastapi.responses import JSONResponse


def check_anthropic_rate_limit(req: Any, client_ip: str) -> JSONResponse | None:
    """简化的速率限制检查（占位符）"""
    # TODO Phase 2: 实现设备场景的速率限制
    return None


async def handle_tool_messages(
    body: dict[str, Any],
    native_stream: Any,
    native_forward: Any,
    maybe_await: Any,
) -> JSONResponse:
    """工具消息处理（占位符）"""
    # TODO Phase 2: 实现设备场景的工具调用
    return JSONResponse(
        status_code=501,
        content={"error": "Tool messages not implemented in device mode"},
    )


def parse_anthropic_messages(body: dict[str, Any], detect_ide: Any) -> Any:
    """解析 Anthropic 消息（占位符）"""
    # TODO Phase 2: 实现设备场景的消息解析
    class ParsedResult:
        messages = body.get("messages", [])

    return ParsedResult()


async def maybe_vision_response(
    body: dict[str, Any],
    parsed: Any,
    req_model: str,
    is_stream: bool,
    request_started_at: float,
    client_ip: str,
    call: Any,
    maybe_await: Any,
) -> Any:
    """视觉响应处理（占位符）"""
    # TODO Phase 2: 实现设备场景的视觉处理
    return None
