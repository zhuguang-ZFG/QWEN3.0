"""
Temporary stub for quality_gate - marked for removal in Phase 2.

战略转型说明：
- 质量门控是编码助手的特性，设备场景不需要
- 这个 stub 仅用于保持现有代码运行
- Phase 2 将完全重构 chat_handler 和 chat_fallback 移除这些依赖
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)


def quality_check(answer: str, query: str, backend: str) -> Tuple[bool, float, List[str]]:
    """
    简化的质量检查 - 总是返回通过。
    设备场景不需要复杂的代码质量门控。

    Returns: (passed, score, issues)
    """
    return (True, 1.0, [])


def default_route(
    messages: List[Dict[str, Any]],
    max_tokens: int,
    stream: bool,
    **kwargs
) -> Tuple[str, str]:
    """
    简化的默认路由 - 返回空后端和答案，让调用者使用正常路由。

    Returns: (backend, answer)
    """
    return ("", "")


def get_same_tier_backends(backend: str, all_backends: List[str]) -> List[str]:
    """
    简化实现 - 返回空列表，禁用同层重试。
    设备场景使用简单的顺序回退即可。
    """
    return []


def get_upgrade_chain(backend: str, all_backends: List[str]) -> List[str]:
    """
    简化实现 - 返回空列表，禁用升级链。
    """
    return []


def honest_failure_response(
    fallback_exhausted: bool,
    last_backend: str,
    request_type: str = "chat"
) -> str:
    """
    诚实的失败响应 - 告诉用户服务暂时不可用。
    """
    return "抱歉，服务暂时不可用，请稍后重试。"


def try_backend(
    backend: str,
    messages: List[Dict[str, Any]],
    max_tokens: int,
    call_fn: Any,
    **kwargs
) -> Tuple[Optional[str], int]:
    """
    简化的后端尝试 - 委托给 call_fn。

    Returns: (answer, status_code)
    """
    try:
        result = call_fn(backend, messages, max_tokens)
        if isinstance(result, tuple):
            return result[0], 200
        return result, 200
    except Exception as exc:
        _log.debug(f"try_backend failed: {type(exc).__name__}")
        return None, 500


# 标记为临时实现
_log.info("quality_gate stub loaded - marked for Phase 2 removal (device-first refactor)")
