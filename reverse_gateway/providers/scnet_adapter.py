"""SCNet Web Chat protocol adapter."""

from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from typing import Any

from reverse_gateway.providers.scnet_cookie import CookieState
from reverse_gateway.providers.scnet_protocol import ProtocolTemplate


SCNET_MODEL_IDS = {
    "qwen3-30b-a3b-instruct-2507": 17,
    "qwen3-30b": 17,
    "minimax-m2.5": 410,
    "minimax-m2_5": 410,
    "qwen3-235b-a22b": 120,
    "qwen3-235b": 120,
    "deepseek-v4-flash": 520,
    "scnet-large-ds-flash": 520,
    "scnet_large_ds_flash": 520,
    "deepseek-v4-pro": 510,
    "scnet-large-ds-pro": 510,
    "scnet_large_ds_pro": 510,
}


def build_headers(template: ProtocolTemplate, cookies: CookieState) -> dict[str, str]:
    headers = dict(template.headers)
    headers.setdefault("Accept", "application/json, text/plain, */*")
    headers.setdefault("Content-Type", "application/json")
    headers.setdefault("Origin", "https://www.scnet.cn")
    headers.setdefault("Referer", "https://www.scnet.cn/ui/chatbot/")
    headers["Cookie"] = cookies.cookie_header()
    return headers


def build_payload(template: ProtocolTemplate, openai_body: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(template.payload_template)
    content = latest_user_content(openai_body)
    transcript = message_transcript(openai_body)
    model = str(openai_body.get("model") or payload.get("model") or "")

    if content:
        _set_first_existing(payload, ("content", "question", "prompt", "message"), content)
    if transcript:
        _set_if_present(payload, ("messages", "history", "conversation"), transcript)
    if model:
        _set_model(payload, model)
    payload["onlineEnable"] = bool(openai_body.get("online", openai_body.get("onlineEnable", True)))
    if "stream" in openai_body:
        payload["stream"] = bool(openai_body.get("stream"))
    for key in ("temperature", "top_p", "topP", "top_k", "topK"):
        if key in openai_body:
            payload[key] = openai_body[key]
    _copy_if_present(openai_body, payload, ("max_tokens", "maxTokens", "metadata"))
    _copy_tool_fields(openai_body, payload)
    # When tools are present, disable web search so the model uses tools
    # instead of answering from built-in knowledge / search results.
    if _has_tools(payload):
        payload["onlineEnable"] = False
    return payload



def attach_text_file(payload: dict[str, Any], file_payload: dict[str, Any], bridge_prompt: str) -> None:
    attach_text_files(payload, [file_payload], bridge_prompt)


def attach_text_files(payload: dict[str, Any], file_payloads: list[dict[str, Any]], bridge_prompt: str) -> None:
    files = payload.get("textFile")
    if not isinstance(files, list):
        files = []
    files.extend(file_payloads)
    payload["textFile"] = files
    _set_first_existing(payload, ("content", "question", "prompt", "message"), bridge_prompt)
    for key in ("history", "messages", "conversation"):
        if key in payload:
            payload[key] = []

def normalize_response(payload: Any, model: str) -> dict[str, Any]:
    text = extract_text(payload)
    return {
        "id": f"chatcmpl-scnet-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or "scnet-web-chat",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def latest_user_content(body: dict[str, Any]) -> str:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return str(body.get("prompt") or body.get("content") or "")
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            return _content_to_text(message.get("content"))
    for message in reversed(messages):
        if isinstance(message, dict):
            return _content_to_text(message.get("content"))
    return ""


def message_transcript(body: dict[str, Any]) -> list[dict[str, str]]:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return []
    transcript = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user")
        content = _content_to_text(message.get("content"))
        if content:
            transcript.append({"role": role, "content": content})
    return transcript


def extract_text(payload: Any) -> str:
    if isinstance(payload, str):
        return extract_sse_text(payload) or payload
    if not isinstance(payload, dict):
        return str(payload)
    if isinstance(payload.get("data"), dict):
        nested = extract_text(payload["data"])
        if nested:
            return nested
    for key in ("content", "answer", "message", "text", "result", "output"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    return ""


def extract_sse_text(text: str) -> str:
    parts: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            item = json.loads(data)
        except json.JSONDecodeError:
            continue
        content = item.get("content") if isinstance(item, dict) else None
        if isinstance(content, str):
            repaired = _repair_mojibake(content)
            if repaired == "[done]":
                continue
            parts.append(repaired)
    return "".join(parts).removesuffix("[done]")


def _repair_mojibake(value: str) -> str:
    try:
        repaired = value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired else value


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "input_text"}:
                parts.append(str(item.get("text") or ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part)
    return str(content or "")


def _set_model(payload: dict[str, Any], model: str) -> None:
    if "model" in payload:
        payload["model"] = model
        return
    if "modelName" in payload:
        payload["modelName"] = model
        return
    if "modelId" not in payload:
        payload["model"] = model
        return
    resolved = SCNET_MODEL_IDS.get(model.strip().lower())
    if resolved is not None:
        payload["modelId"] = resolved
        return
    try:
        payload["modelId"] = int(model)
    except ValueError:
        return


def _set_first_existing(payload: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    for key in keys:
        if key in payload:
            payload[key] = value
            return
    payload[keys[0]] = value


def _set_if_present(payload: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    for key in keys:
        if key in payload:
            payload[key] = value
            return


def _copy_if_present(source: dict[str, Any], target: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        if key in source and key in target:
            target[key] = source[key]


def _has_tools(payload: dict[str, Any]) -> bool:
    """Check if payload has any tool/MCP configuration."""
    for key in ("tools", "toolList", "mcpServers", "mcp_servers"):
        if payload.get(key):
            return True
    return False


def _copy_tool_fields(source: dict[str, Any], target: dict[str, Any]) -> None:
    mappings = {
        "tools": ("tools", "toolList"),
        "tool_choice": ("tool_choice", "toolChoice"),
        "mcp_servers": ("mcp_servers", "mcpServers"),
        "mcp_context": ("mcp_context", "mcpContext"),
    }
    for source_key, target_keys in mappings.items():
        if source_key not in source:
            continue
        for target_key in target_keys:
            if target_key in target:
                target[target_key] = source[source_key]
                break
