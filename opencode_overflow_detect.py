"""opencode_overflow_detect.py — 增强型上下文溢出检测。

复刻 OpenCode provider/error.ts 的 OVERFLOW_PATTERNS + isOverflow() (L24-62)。

与 opencode_error_adapter.py 的区别:
- 本模块提供独立的 is_overflow_error() 函数，接口更清晰
- 支持从异常对象、HTTP 响应、SSE 事件等多种输入格式检测
- 增加 provider 级别的特殊模式 (如 Copilot 400 no-body, vLLM 空响应)
- 提供 classify_overflow_severity() 用于路由决策

源码参考:
  - opencode-source/packages/opencode/src/provider/error.ts (L24-62)
  - opencode-source/packages/opencode/src/session/overflow.ts
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

_log = logging.getLogger(__name__)

# ── 完整溢出模式库 (error.ts:24-44) ─────────────────────────────────────────
# 按 provider 分组，便于日志诊断
_PROVIDER_OVERFLOW_PATTERNS: dict[str, list[re.Pattern]] = {
    "anthropic": [
        re.compile(r"prompt is too long", re.IGNORECASE),
    ],
    "bedrock": [
        re.compile(r"input is too long for requested model", re.IGNORECASE),
    ],
    "openai": [
        re.compile(r"exceeds the context window", re.IGNORECASE),
        re.compile(r"reduce your input", re.IGNORECASE),
    ],
    "google": [
        re.compile(r"input token count.*exceeds the maximum", re.IGNORECASE),
        re.compile(r"exceeds the maximum number of tokens", re.IGNORECASE),
    ],
    "xai": [
        re.compile(r"maximum prompt length is \d+", re.IGNORECASE),
    ],
    "groq": [
        re.compile(r"reduce the length of the messages", re.IGNORECASE),
    ],
    "openrouter": [
        re.compile(r"maximum context length is \d+ tokens", re.IGNORECASE),
    ],
    "deepseek": [
        re.compile(r"maximum context length is \d+ tokens", re.IGNORECASE),
    ],
    "copilot": [
        re.compile(r"exceeds the limit of \d+", re.IGNORECASE),
    ],
    "vllm": [
        re.compile(r"maximum context length is \d+ tokens", re.IGNORECASE),
        re.compile(r"context length is only \d+ tokens", re.IGNORECASE),
        re.compile(r"input length.*exceeds.*context length", re.IGNORECASE),
    ],
    "llamacpp": [
        re.compile(r"exceeds the available context size", re.IGNORECASE),
    ],
    "lmstudio": [
        re.compile(r"greater than the context length", re.IGNORECASE),
    ],
    "minimax": [
        re.compile(r"context window exceeds limit", re.IGNORECASE),
    ],
    "kimi": [
        re.compile(r"exceeded model token limit", re.IGNORECASE),
    ],
    "ollama": [
        re.compile(r"prompt too long; exceeded (?:max )?context length", re.IGNORECASE),
    ],
    "mistral": [
        re.compile(r"too large for model with \d+ maximum context length", re.IGNORECASE),
    ],
    "zai": [
        re.compile(r"model_context_window_exceeded", re.IGNORECASE),
    ],
    "generic": [
        re.compile(r"context[_ ]length[_ ]exceeded", re.IGNORECASE),
        re.compile(r"request entity too large", re.IGNORECASE),
        re.compile(r"context length exceeded", re.IGNORECASE),
    ],
}

# 扁平化所有模式为单一列表 (用于快速匹配)
_ALL_OVERFLOW_PATTERNS: list[re.Pattern] = []
for _patterns in _PROVIDER_OVERFLOW_PATTERNS.values():
    _ALL_OVERFLOW_PATTERNS.extend(_patterns)

# 去重 (有些 provider 共享相同模式)
_seen: set[str] = set()
_UNIQUE_PATTERNS: list[re.Pattern] = []
for _p in _ALL_OVERFLOW_PATTERNS:
    if _p.pattern not in _seen:
        _seen.add(_p.pattern)
        _UNIQUE_PATTERNS.append(_p)

# ── No-body 状态码模式 (error.ts:58-62) ────────────────────────────────────
# Cerebras/Mistral often return "400 (no body)" / "413 (no body)" on overflow
_NO_BODY_PATTERN = re.compile(
    r"^4(00|13)\s*(status code)?\s*\(no body\)", re.IGNORECASE,
)


def is_overflow_error(
    error_message: str = "",
    status_code: int | None = None,
    response_body: str | None = None,
    error_code: str | None = None,
) -> bool:
    """检测是否为上下文溢出错误。

    增强的检测逻辑 (error.ts:46-100):
    1. HTTP 413 → 直接判定溢出
    2. error.code == "context_length_exceeded" → 直接判定
    3. 20+ 正则模式匹配错误消息
    4. 400/403 no-body → 某些后端在溢出时不返回 body

    Args:
        error_message: 错误消息文本。
        status_code: HTTP 状态码。
        response_body: 原始响应体 JSON 字符串。
        error_code: 错误码 (如 "context_length_exceeded")。

    Returns:
        True 表示检测到上下文溢出。
    """
    # 1. HTTP 413
    if status_code == 413:
        return True

    # 2. error.code 直接匹配
    if error_code and error_code.lower() == "context_length_exceeded":
        return True

    # 3. 从 response_body 提取
    if response_body:
        try:
            body = json.loads(response_body)
            if isinstance(body, dict):
                err = body.get("error") or {}
                if isinstance(err, dict):
                    code = err.get("code", "")
                    if isinstance(code, str) and code.lower() == "context_length_exceeded":
                        return True
                    err_msg = err.get("message", "")
                    if isinstance(err_msg, str) and _match_patterns(err_msg):
                        return True
                elif isinstance(body.get("error"), str):
                    if _match_patterns(body["error"]):
                        return True
        except (json.JSONDecodeError, TypeError):
            pass

    # 4. 正则匹配错误消息
    if error_message and _match_patterns(error_message):
        return True

    # 5. No-body 400/403 模式
    if error_message and _NO_BODY_PATTERN.search(error_message):
        return True

    return False


def _match_patterns(text: str) -> bool:
    """检查文本是否匹配任何溢出模式。"""
    for pattern in _UNIQUE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def identify_overflow_provider(error_message: str) -> str | None:
    """识别溢出错误来自哪个 provider 族。

    用于日志诊断和路由决策。

    Args:
        error_message: 错误消息文本。

    Returns:
        provider 名称 (如 "anthropic", "openai") 或 None。
    """
    if not error_message:
        return None
    for provider, patterns in _PROVIDER_OVERFLOW_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(error_message):
                return provider
    return None


def classify_overflow_severity(
    error_message: str = "",
    status_code: int | None = None,
    response_body: str | None = None,
) -> str:
    """分类溢出严重程度，用于路由决策。

    Returns:
        "hard" — 确定性溢出 (413, context_length_exceeded code)
        "soft" — 模式匹配溢出 (可能是暂时性问题)
        "none" — 非溢出
    """
    if status_code == 413:
        return "hard"

    if response_body:
        try:
            body = json.loads(response_body)
            if isinstance(body, dict):
                err = body.get("error") or {}
                if isinstance(err, dict):
                    code = err.get("code", "")
                    if isinstance(code, str) and code.lower() == "context_length_exceeded":
                        return "hard"
        except (json.JSONDecodeError, TypeError):
            pass

    if is_overflow_error(error_message, status_code, response_body):
        return "soft"

    return "none"


def is_overflow_from_exception(exc: Exception) -> bool:
    """从异常对象检测是否为溢出错误。

    便捷方法，从异常的 message/status_code/response 属性提取信息。

    Args:
        exc: 异常对象 (httpx.HTTPStatusError, openai.APIError 等)。

    Returns:
        True 表示溢出。
    """
    msg = str(exc)
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    body = None

    # httpx.HTTPStatusError
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            body = response.text
        except Exception:
            _log.debug("overflow_detect: response text read failed", exc_info=True)
        if status is None:
            status = getattr(response, "status_code", None)

    # openai APIError
    if status is None:
        status = getattr(exc, "http_status", None)

    error_code = getattr(exc, "code", None)

    return is_overflow_error(
        error_message=msg,
        status_code=status,
        response_body=body,
        error_code=error_code,
    )
