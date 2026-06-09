"""
Temporary stub for anthropic_vision_sse - marked for Phase 2 removal.

战略转型说明：
- Anthropic Vision SSE 是编码助手专属特性
- 设备场景使用统一的视觉处理流程
- Phase 2 将完全重构移除这些依赖
"""

import logging
from typing import Any, Dict, List
from fastapi.responses import StreamingResponse

_log = logging.getLogger(__name__)


async def anthropic_vision_messages(
    messages: List[Dict[str, Any]],
    model: str,
    max_tokens: int,
    temperature: float = 0.7,
    **kwargs
) -> StreamingResponse:
    """
    简化实现 - 抛出异常，表示不支持。
    设备场景应该使用标准的视觉处理接口。
    """
    raise NotImplementedError(
        "Anthropic Vision SSE is deprecated in device-first architecture. "
        "Use standard vision API endpoints instead."
    )


_log.info("anthropic_vision_sse stub loaded - marked for Phase 2 removal")
