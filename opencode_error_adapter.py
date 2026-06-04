"""OpenCode 错误适配 — 检测上下文溢出错误并返回兼容格式。

移植自 opencode-source/packages/opencode/src/provider/error.ts。

核心功能:
1. detect_context_overflow() — 用 18+ 种正则匹配后端错误消息
2. build_overflow_response() — 构建 OpenCode 可识别的 context_overflow 错误响应
"""

from __future__ import annotations

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

    Args:
        error_message: 后端返回的原始错误消息文本。
        status_code: HTTP 状态码（可选）。
                    413 自动视为溢出，400/403 需配合正则检测。
        response_body: 后端返回的原始响应体 JSON 字符串（可选）。
                       用于检查 error.code === "context_length_exceeded"。

    Returns:
        若检测到上下文溢出则返回 True。
    """
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
