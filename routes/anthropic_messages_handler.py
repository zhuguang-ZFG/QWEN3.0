"""
Temporary stub for anthropic_messages_handler - marked for Phase 2 removal.

@deprecated Phase 2 removal — use OpenAI-compatible /v1/chat/completions instead.

战略转型说明：
- Anthropic Messages API 是编码助手专属特性
- 设备场景使用标准 OpenAI 兼容接口
- Phase 2 将完全重构 chat_endpoints 移除这些依赖
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)


def check_anthropic_rate_limit(headers: Dict[str, str]) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    简化实现 - 不执行速率限制检查。
    设备场景使用统一的后端速率限制机制。

    Returns: (is_rate_limited, error_response)
    """
    return (False, None)


async def handle_tool_messages(
    body: Dict[str, Any],
    *,
    native_stream: Callable[..., Any],
    native_forward: Callable[..., Any],
    maybe_await: Callable[..., Any],
) -> Any:
    """
    @deprecated Phase 2 removal — Anthropic 工具转发已移除，请使用 OpenAI 兼容接口。
    """
    raise NotImplementedError(
        "Anthropic tool message forwarding is deprecated in device-first architecture. "
        "Use standard OpenAI-compatible tool APIs instead."
    )


def maybe_vision_response(
    messages: List[Dict[str, Any]],
    model: str,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    简化实现 - 返回 None，禁用 Anthropic 专属视觉处理。
    设备场景使用统一的多模态处理流程。
    """
    return None


def parse_anthropic_messages(
    body: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    简化实现 - 假设消息已经是标准格式。

    Returns: (messages, metadata)
    """
    messages = body.get("messages", [])
    metadata = {
        "model": body.get("model", ""),
        "max_tokens": body.get("max_tokens", 4000),
        "temperature": body.get("temperature", 0.7),
        "stream": body.get("stream", False),
    }
    return (messages, metadata)


_log.info("anthropic_messages_handler stub loaded - marked for Phase 2 removal")
