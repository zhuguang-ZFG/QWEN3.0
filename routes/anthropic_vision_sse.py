"""
Anthropic vision SSE - Simplified stub for strategic pivot.

原 anthropic_vision_sse.py 已删除（编码助手专属）。
此文件提供最小占位符，避免大量修改 routes/chat_endpoints.py。
Phase 2 将重构为设备场景专用的视觉处理。
"""
from typing import AsyncIterator


async def anthropic_vision_messages(
    chat_id: str,
    content: str,
    model: str = "vision-stub",
) -> AsyncIterator[str]:
    """视觉消息 SSE 流（占位符）"""
    # TODO Phase 2: 实现设备场景的视觉流式响应
    yield f"data: {{'type':'error','message':'Vision SSE not implemented in device mode'}}\n\n"
