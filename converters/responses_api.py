"""OpenAI Responses API to Chat Completions adapter for OpenCode."""

from __future__ import annotations

import time
import uuid
from typing import Any

from converters.responses_content import (
    content_to_text,
    is_replay_metadata_item,
    tool_output_continuation_text,
)
from converters.responses_stream_transform import transform_chat_sse_iter, transform_chat_sse_stream
from converters.responses_usage import chat_usage_to_responses_usage


def _new_response_id() -> str:
    return f"resp_{uuid.uuid4().hex[:24]}"


def _new_item_id(prefix: str = "msg") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _convert_input_item(item: dict) -> list[dict]:
    """Map one Responses API input item to chat message(s)."""
    ptype = item.get("type", "")
    if is_replay_metadata_item(item):
        return []
    if ptype == "function_call_output":
        return [{"role": "user", "content": tool_output_continuation_text(item)}]
    if ptype == "function_call":
        return [_function_call_message(item)]

    role = item.get("role", "user")
    if role == "developer":
        role = "system"

    content = item.get("content")
    if isinstance(content, list):
        return _convert_content_list(role, content)
    return [{"role": role, "content": content_to_text(content)}]


def _function_call_message(item: dict) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": item.get("call_id") or item.get("id") or _new_item_id("call"),
            "type": "function",
            "function": {
                "name": item.get("name", ""),
                "arguments": item.get("arguments", "{}"),
            },
        }],
    }


def _convert_content_list(role: str, content: list) -> list[dict]:
    tool_msgs: list[dict] = []
    text_parts: list[str] = []
    tool_output_parts: list[dict] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        ptype = part.get("type", "")
        if ptype in ("input_text", "output_text", "text"):
            text_parts.append(str(part.get("text", "") or ""))
        elif ptype == "function_call":
            tool_msgs.append(_function_call_message(part))
        elif ptype == "function_call_output":
            tool_msgs.append({
                "role": "tool",
                "tool_call_id": part.get("call_id", ""),
                "content": content_to_text(part.get("output", "")),
            })
            tool_output_parts.append(part)
        elif ptype == "input_image":
            text_parts.append(content_to_text([part]))

    if not text_parts and tool_msgs and all(msg["role"] == "tool" for msg in tool_msgs):
        content_text = "\n\n".join(
            tool_output_continuation_text(part) for part in tool_output_parts
        )
        return [{"role": "user", "content": content_text}]

    msgs: list[dict] = []
    if text_parts:
        msgs.append({"role": role, "content": "\n".join(text_parts)})
    msgs.extend(tool_msgs)
    return msgs


def _convert_tools(tools: list | None) -> list[dict] | None:
    if not tools:
        return None
    out: list[dict] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") == "function" and "function" not in tool and "name" in tool:
            out.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            })
        else:
            out.append(tool)
    return out or None


def responses_body_to_chat(body: dict) -> dict:
    """Convert POST /v1/responses body to /v1/chat/completions body."""
    messages: list[dict] = []

    instructions = str(body.get("instructions") or "").strip()
    if instructions:
        messages.append({"role": "system", "content": instructions})

    raw_input = body.get("input")
    if isinstance(raw_input, str) and raw_input.strip():
        messages.append({"role": "user", "content": raw_input})
    elif isinstance(raw_input, list):
        for item in raw_input:
            if isinstance(item, dict):
                messages.extend(_convert_input_item(item))
            elif isinstance(item, str) and item.strip():
                messages.append({"role": "user", "content": item})

    if not messages:
        messages.append({"role": "user", "content": " "})

    chat: dict[str, Any] = {
        "model": body.get("model", "lima-1.3"),
        "messages": messages,
        "stream": bool(body.get("stream", False)),
    }

    max_out = body.get("max_output_tokens")
    if max_out is not None:
        chat["max_tokens"] = max_out
    elif body.get("max_tokens") is not None:
        chat["max_tokens"] = body["max_tokens"]

    reasoning = body.get("reasoning")
    if isinstance(reasoning, dict) and reasoning.get("effort"):
        chat["reasoning_effort"] = reasoning["effort"]

    tools = _convert_tools(body.get("tools"))
    if tools:
        chat["tools"] = tools

    if body.get("tool_choice") is not None:
        chat["tool_choice"] = body["tool_choice"]

    if body.get("temperature") is not None:
        chat["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        chat["top_p"] = body["top_p"]

    return chat


def chat_completion_to_response(data: dict) -> dict:
    """Convert chat.completion JSON to Responses API response object."""
    resp_id = _new_response_id()
    created = int(data.get("created") or time.time())
    model = data.get("model", "lima-1.3")
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    tool_calls = message.get("tool_calls") or []

    output: list[dict] = []
    if content:
        output.append({
            "type": "message",
            "id": _new_item_id("msg"),
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": content}],
        })

    for tc in tool_calls:
        fn = tc.get("function") or {}
        output.append({
            "type": "function_call",
            "id": _new_item_id("fc"),
            "call_id": tc.get("id") or _new_item_id("call"),
            "name": fn.get("name", ""),
            "arguments": fn.get("arguments", "{}"),
            "status": "completed",
        })

    return {
        "id": resp_id,
        "object": "response",
        "created_at": created,
        "model": model,
        "status": "completed",
        "output": output,
        "usage": chat_usage_to_responses_usage(data.get("usage")),
        "parallel_tool_calls": True,
    }
