"""OpenCode 错误适配 — 检测上下文溢出错误并返回兼容格式。

移植自 opencode-source/packages/opencode/src/provider/error.ts。

核心功能:
1. detect_context_overflow() — 用 20 种正则匹配后端错误消息
2. build_overflow_response() — 构建 OpenCode 可识别的 context_overflow 错误响应
3. parse_stream_error() — SSE 流错误结构化解析
4. parse_api_error() — API 调用错误解析（含 HTML 网关检测）
5. HeaderTimeoutError / ResponseStreamError — SSE 超时错误类
"""
from __future__ import annotations


import logging

_log = logging.getLogger(__name__)
import json
import re
from typing import Any

# 移植自 error.ts OVERFLOW_PATTERNS (L24-44)
# 覆盖：Anthropic, OpenAI, Google, Groq, xAI, OpenRouter, DeepSeek,
#       vLLM, GitHub Copilot, llama.cpp, LM Studio, MiniMax, Moonshot,
#       Mistral, Ollama, z.ai 等
_OVERFLOW_PATTERNS: list[re.Pattern] = [
    re.compile(r"prompt is too long", re.IGNORECASE),                     # Anthropic
    re.compile(r"input is too long for requested model", re.IGNORECASE),  # Amazon Bedrock
    re.compile(r"exceeds the context window", re.IGNORECASE),             # OpenAI
    re.compile(r"input token count.*exceeds the maximum", re.IGNORECASE), # Google Gemini
    re.compile(r"maximum prompt length is \d+", re.IGNORECASE),           # xAI Grok
    re.compile(r"reduce the length of the messages", re.IGNORECASE),      # Groq
    re.compile(r"maximum context length is \d+ tokens", re.IGNORECASE),   # OpenRouter, DeepSeek, vLLM
    re.compile(r"exceeds the limit of \d+", re.IGNORECASE),               # GitHub Copilot
    re.compile(r"exceeds the available context size", re.IGNORECASE),     # llama.cpp
    re.compile(r"greater than the context length", re.IGNORECASE),        # LM Studio
    re.compile(r"context window exceeds limit", re.IGNORECASE),           # MiniMax
    re.compile(r"exceeded model token limit", re.IGNORECASE),             # Kimi/Moonshot
    re.compile(r"context[_ ]length[_ ]exceeded", re.IGNORECASE),          # Generic fallback
    re.compile(r"request entity too large", re.IGNORECASE),               # HTTP 413
    re.compile(r"context length is only \d+ tokens", re.IGNORECASE),      # vLLM
    re.compile(r"input length.*exceeds.*context length", re.IGNORECASE),  # vLLM
    re.compile(r"prompt too long; exceeded (?:max )?context length", re.IGNORECASE),  # Ollama
    re.compile(r"too large for model with \d+ maximum context length", re.IGNORECASE),  # Mistral
    re.compile(r"model_context_window_exceeded", re.IGNORECASE),          # z.ai
    re.compile(r"context length exceeded", re.IGNORECASE),                # Additional generic
]


def detect_context_overflow(
    error_message: str,
    status_code: int | None = None,
    response_body: str | None = None,
) -> bool:
    """检测错误消息是否表示上下文溢出。

    优先使用增强检测模块 (opencode_overflow_detect)，回退到本地模式库。

    Args:
        error_message: 后端返回的原始错误消息文本。
        status_code: HTTP 状态码（可选）。
                    413 自动视为溢出，400/403 需配合正则检测。
        response_body: 后端返回的原始响应体 JSON 字符串（可选）。
                       用于检查 error.code === "context_length_exceeded"。

    Returns:
        若检测到上下文溢出则返回 True。
    """
    # M-OC11: 优先使用增强溢出检测模块
    try:
        from opencode_overflow_detect import is_overflow_error
        if is_overflow_error(
            error_message=error_message,
            status_code=status_code,
            response_body=response_body,
        ):
            return True
    except ImportError:
        _log.debug("opencode_error_adapter: optional module not available", exc_info=True)
    # HTTP 413 = Request Entity Too Large → 上下文溢出
    if status_code == 413:
        return True

    # 检查响应体 JSON 中的 error.code
    if response_body:
        try:
            body = json.loads(response_body)
            if isinstance(body, dict):
                error = body.get("error") or {}
                if isinstance(error, dict) and error.get("code") == "context_length_exceeded":
                    return True
                if isinstance(body.get("error"), str):
                    error_msg = body["error"]
                    for pattern in _OVERFLOW_PATTERNS:
                        if pattern.search(error_msg):
                            return True
        except (json.JSONDecodeError, TypeError):
            pass

    # 正则检测错误消息
    for pattern in _OVERFLOW_PATTERNS:
        if pattern.search(error_message):
            return True

    # 400/403 (no body) 模式 — 某些后端在溢出时不返回 body
    if re.search(r"^4(00|03)\s*(status code)?\s*\(no body\)", error_message, re.IGNORECASE):
        return True

    return False


def build_overflow_response(
    message: str = "Input exceeds context window of this model",
    model: str = "lima-1.3",
) -> dict:
    """构建 OpenCode 可识别的 context_overflow OpenAI 格式错误响应。

    OpenCode 的 parseStreamError() 会在响应中查找:
        {"type": "error", "error": {"code": "context_length_exceeded", ...}}
    此函数返回的 dict 可直接转为 JSONResponse(status_code=413/400)。

    Args:
        message: 人类可读的错误描述。
        model:   模型标识符。

    Returns:
        符合 OpenAI ChatCompletion 错误格式的 dict。
    """
    return {
        "error": {
            "code": "context_length_exceeded",
            "message": message,
            "type": "invalid_request_error",
            "param": None,
        }
    }


def build_overflow_sse_chunk(
    message: str = "Input exceeds context window of this model",
) -> str:
    """构建 OpenAI SSE 格式的上下文溢出错误事件。

    返回格式: data: {"type":"error","error":{"code":"context_length_exceeded",...}}
    """
    import time

    payload = {
        "id": "chatcmpl-overflow",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "lima-1.3",
        "choices": [],
        "type": "error",
        "error": {
            "code": "context_length_exceeded",
            "message": message,
        },
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def extract_overflow_message(exc: Exception) -> str:
    """从异常中提取最适合展示的溢出错误消息。
    
    优先使用异常的 status_code 和消息文本。
    """
    status = ""
    for attr in ("status_code", "code", "status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            status = f" (status {val})"
            break
    return f"Input exceeds context window of this model{status}"


def parse_stream_error(raw: str) -> dict[str, Any] | None:
    """解析 SSE 流中的错误事件，返回结构化错误信息。

    移植自 OpenCode error.ts parseStreamError() (L134-179)。
    识别的错误码：
      - context_length_exceeded → type="context_overflow"
      - insufficient_quota     → type="api_error", isRetryable=False
      - usage_not_included     → type="api_error", isRetryable=False
      - invalid_prompt         → type="api_error", isRetryable=False
      - server_is_overloaded   → type="api_error", isRetryable=True
      - server_error           → type="api_error", isRetryable=True

    Args:
        raw: SSE 事件体的字符串（含 type/error 字段的 JSON）。

    Returns:
        结构化错误 dict，或 None（若非错误事件或无法解析）。
    """
    try:
        body: dict[str, Any] = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None

    # 部分 SSE 错误将 JSON 嵌套在 message 字段中
    if isinstance(body.get("message"), str):
        try:
            inner = json.loads(body["message"])
            if isinstance(inner, dict):
                body = inner
        except (json.JSONDecodeError, TypeError):
            pass

    if body.get("type") != "error":
        return None

    code = (body.get("error") or {}).get("code") if isinstance(body.get("error"), dict) else None
    response_body = json.dumps(body, ensure_ascii=False)

    if code == "context_length_exceeded":
        return {
            "type": "context_overflow",
            "message": "Input exceeds context window of this model",
            "responseBody": response_body,
        }
    if code == "insufficient_quota":
        return {
            "type": "api_error",
            "message": "Quota exceeded. Check your plan and billing details.",
            "isRetryable": False,
            "responseBody": response_body,
        }
    if code == "usage_not_included":
        return {
            "type": "api_error",
            "message": "To use Codex with your ChatGPT plan, upgrade to Plus: https://chatgpt.com/explore/plus.",
            "isRetryable": False,
            "responseBody": response_body,
        }
    if code == "invalid_prompt":
        err_msg = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else None
        return {
            "type": "api_error",
            "message": err_msg if isinstance(err_msg, str) else "Invalid prompt.",
            "isRetryable": False,
            "responseBody": response_body,
        }
    if code in ("server_is_overloaded", "server_error"):
        err_msg = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else None
        return {
            "type": "api_error",
            "message": err_msg if isinstance(err_msg, str) else "Server error.",
            "isRetryable": True,
            "responseBody": response_body,
        }

    return None


def parse_api_error(
    error_obj: dict[str, Any],
    status_code: int = 0,
    response_headers: dict[str, str] | None = None,
    response_body: str = "",
    url: str = "",
) -> dict[str, Any]:
    """解析 API 调用错误，返回结构化的错误信息。

    移植自 OpenCode error.ts parseAPICallError() (L197-218)。

    Args:
        error_obj: 后端返回的 error dict（含 message/code 字段）。
        status_code: HTTP 状态码。
        response_headers: 响应头字典。
        response_body: 响应体 JSON 字符串。
        url: 请求 URL（用于元数据）。

    Returns:
        type="context_overflow" | type="api_error" 的结构化 dict。
    """
    msg = str(error_obj.get("message", "Unknown API error"))
    is_overflow = detect_context_overflow(msg, status_code, response_body)
    try:
        body = json.loads(response_body) if isinstance(response_body, str) else None
    except (json.JSONDecodeError, TypeError):
        body = None

    if is_overflow:
        return {
            "type": "context_overflow",
            "message": msg,
            "responseBody": response_body,
        }

    metadata: dict[str, str] = {}
    if url:
        metadata["url"] = url

    is_retryable = error_obj.get("isRetryable", False)

    return {
        "type": "api_error",
        "message": msg,
        "statusCode": status_code or error_obj.get("statusCode", 0),
        "isRetryable": bool(is_retryable),
        "responseHeaders": response_headers or {},
        "responseBody": response_body,
        "metadata": metadata,
    }


# ── Timeout error classes (error.ts L11-19) ──────────────────────────────────

class HeaderTimeoutError(Exception):
    """Raised when response headers take too long to arrive (error.ts:11-14)."""

    def __init__(self, url: str, timeout_ms: int) -> None:
        self.url = url
        self.timeout_ms = timeout_ms
        super().__init__(f"Timeout waiting for headers from {url} after {timeout_ms}ms")


class ResponseStreamError(Exception):
    """Raised on SSE read timeouts inside wrapSSE() (error.ts:16-19)."""

    def __init__(self, url: str, timeout_ms: int, chunks_received: int = 0) -> None:
        self.url = url
        self.timeout_ms = timeout_ms
        self.chunks_received = chunks_received
        super().__init__(
            f"Timeout reading stream from {url} after {timeout_ms}ms "
            f"({chunks_received} chunks received)"
        )


# ── OpenAI retryable detection (error.ts:46-49) ──────────────────────────────

def is_openai_error_retryable(status_code: int) -> bool:
    """Check if an OpenAI error status code is retryable.

    Ported from error.ts isOpenAiErrorRetryable().
    OpenAI 404 is retryable because models can become available mid-request.
    """
    return status_code == 404


# ── Error message builder (error.ts:56-88) ───────────────────────────────────

_HTML_DETECT_RE = re.compile(r"<(!doctype|\s*html)", re.IGNORECASE)


def message(error_body: Any, status_code: int = 0, url: str = "") -> str:
    """Build a user-readable error message from a raw error body.

    Ported from error.ts message() (L56-88).
    Handles: empty messages, status code text fallback, HTML proxy detection.
    """
    msg = ""
    if isinstance(error_body, dict):
        err = error_body.get("error") or {}
        msg = str(err.get("message", "") if isinstance(err, dict) else err).strip()
    elif isinstance(error_body, str):
        msg = error_body.strip()

    # Empty message → use status code
    if not msg and status_code:
        msg = f"{status_code}"

    if not msg and url:
        msg = f"Error response from {url}"

    # HTML body detection (error.ts:79-85)
    if _HTML_DETECT_RE.search(msg):
        if status_code == 401:
            msg = "Authentication token is missing. Are you signed in?"
        elif status_code == 403:
            msg = "You do not have permissions to use this model. Try selecting a different model."
        else:
            # Try to extract a meaningful message from JSON error body
            if isinstance(error_body, dict):
                err = error_body.get("error") or {}
                if isinstance(err, dict) and err.get("message"):
                    msg = str(err["message"])
            if _HTML_DETECT_RE.search(msg):
                return f"{status_code}"
        return msg

    if not msg:
        return f"{status_code}"

    return msg


# ── Enhanced parse_api_error with HTML detection ─────────────────────────────

def parse_api_error_v2(
    error_obj: dict[str, Any],
    status_code: int = 0,
    response_headers: dict[str, str] | None = None,
    response_body: str = "",
    url: str = "",
) -> dict[str, Any]:
    """Enhanced API error parser with HTML gateway detection and retryable logic.

    Builds on parse_api_error() with:
    - HTML body gateway detection (401 → auth, 403 → permissions)
    - OpenAI 404 retryable detection
    - URL metadata from actual request context
    """
    # Use message() builder for proper error text
    try:
        body = json.loads(response_body) if isinstance(response_body, str) and response_body else None
    except (json.JSONDecodeError, TypeError):
        body = response_body

    msg = message(body or error_obj, status_code, url)
    is_overflow = detect_context_overflow(msg, status_code, response_body)

    if is_overflow:
        return {
            "type": "context_overflow",
            "message": msg,
            "responseBody": response_body,
        }

    metadata: dict[str, str] = {}
    if url:
        metadata["url"] = url

    # Determine retryability (error.ts:46-49 + L211-217)
    is_retryable = bool(
        error_obj.get("isRetryable", False)
        or is_openai_error_retryable(status_code)
    )

    return {
        "type": "api_error",
        "message": msg,
        "statusCode": status_code or error_obj.get("statusCode", 0),
        "isRetryable": is_retryable,
        "responseHeaders": response_headers or {},
        "responseBody": response_body,
        "metadata": metadata,
    }
