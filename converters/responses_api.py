"""OpenAI Responses API ↔ Chat Completions adapter (OpenCode Build /v1/responses)."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any


def _new_response_id() -> str:
    return f"resp_{uuid.uuid4().hex[:24]}"


def _new_item_id(prefix: str = "msg") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _text_from_part(part: dict) -> str:
    ptype = part.get("type", "")
    if ptype in ("input_text", "output_text", "text"):
        return str(part.get("text", "") or "")
    if ptype == "input_image":
        return "[image]"
    return ""


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [_text_from_part(p) for p in content if isinstance(p, dict)]
        return "\n".join(p for p in parts if p)
    return str(content)


def _tool_output_continuation_text(item: dict) -> str:
    call_id = str(item.get("call_id") or item.get("id") or "unknown")
    output = str(item.get("output", "") or "")
    return (
        f"Tool output for call {call_id}:\n"
        f"{output}\n\n"
        "Continue from this tool result and answer the user's request."
    )


def _convert_input_item(item: dict) -> list[dict]:
    """Map one Responses API input item to chat message(s)."""
    ptype = item.get("type", "")
    if ptype == "function_call_output":
        return [{"role": "user", "content": _tool_output_continuation_text(item)}]
    if ptype == "function_call":
        return [{
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
        }]

    role = item.get("role", "user")
    if role == "developer":
        role = "system"

    content = item.get("content")
    if isinstance(content, list):
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
                tool_msgs.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": part.get("call_id") or part.get("id") or _new_item_id("call"),
                        "type": "function",
                        "function": {
                            "name": part.get("name", ""),
                            "arguments": part.get("arguments", "{}"),
                        },
                    }],
                })
            elif ptype == "function_call_output":
                tool_msgs.append({
                    "role": "tool",
                    "tool_call_id": part.get("call_id", ""),
                    "content": str(part.get("output", "") or ""),
                })
                tool_output_parts.append(part)
            elif ptype == "input_image":
                text_parts.append("[image]")
        if not text_parts and tool_msgs and all(msg["role"] == "tool" for msg in tool_msgs):
            content_text = "\n\n".join(
                _tool_output_continuation_text(part) for part in tool_output_parts
            )
            return [{"role": "user", "content": content_text}]
        msgs: list[dict] = []
        if text_parts:
            msgs.append({"role": role, "content": "\n".join(text_parts)})
        msgs.extend(tool_msgs)
        return msgs

    return [{"role": role, "content": _content_to_text(content)}]


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

    usage_raw = data.get("usage") or {}
    usage = {
        "input_tokens": usage_raw.get("prompt_tokens", 0),
        "output_tokens": usage_raw.get("completion_tokens", 0),
        "total_tokens": usage_raw.get("total_tokens", 0),
    }

    return {
        "id": resp_id,
        "object": "response",
        "created_at": created,
        "model": model,
        "status": "completed",
        "output": output,
        "usage": usage,
        "parallel_tool_calls": True,
    }


def _sse_event(event_type: str, payload: dict) -> str:
    payload = dict(payload)
    payload.setdefault("type", event_type)
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ResponsesStreamConverter:
    """Transform chat.completion.chunk SSE into Responses API SSE events."""

    def __init__(self, *, model: str = "lima-1.3") -> None:
        self.response_id = _new_response_id()
        self.model = model
        self.created_at = int(time.time())
        self.started = False
        self.message_item_id = _new_item_id("msg")
        self.text_part_started = False
        self.tool_items: dict[int, dict] = {}
        self.finish_reason: str | None = None
        self.usage: dict | None = None

    def bootstrap_events(self) -> list[str]:
        return [
            _sse_event("response.created", {
                "response": {
                    "id": self.response_id,
                    "object": "response",
                    "status": "in_progress",
                    "created_at": self.created_at,
                    "model": self.model,
                },
            }),
            _sse_event("response.in_progress", {
                "response": {
                    "id": self.response_id,
                    "status": "in_progress",
                },
            }),
        ]

    def _ensure_message_item(self) -> list[str]:
        if self.text_part_started:
            return []
        self.text_part_started = True
        return [
            _sse_event("response.output_item.added", {
                "output_index": 0,
                "item": {
                    "type": "message",
                    "id": self.message_item_id,
                    "status": "in_progress",
                    "role": "assistant",
                    "content": [],
                },
            }),
            _sse_event("response.content_part.added", {
                "item_id": self.message_item_id,
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": ""},
            }),
        ]

    def feed_chat_chunk(self, chunk: dict) -> list[str]:
        events: list[str] = []
        if chunk.get("model"):
            self.model = chunk["model"]
        if chunk.get("usage"):
            u = chunk["usage"]
            self.usage = {
                "input_tokens": u.get("prompt_tokens", 0),
                "output_tokens": u.get("completion_tokens", 0),
                "total_tokens": u.get("total_tokens", 0),
            }

        for choice in chunk.get("choices") or []:
            if choice.get("finish_reason"):
                self.finish_reason = choice["finish_reason"]
            delta = choice.get("delta") or {}
            if delta.get("content"):
                events.extend(self._ensure_message_item())
                events.append(_sse_event("response.output_text.delta", {
                    "item_id": self.message_item_id,
                    "output_index": 0,
                    "content_index": 0,
                    "delta": delta["content"],
                }))
            for tc in delta.get("tool_calls") or []:
                events.extend(self._feed_tool_delta(tc))
        return events

    def _feed_tool_delta(self, tc: dict) -> list[str]:
        events: list[str] = []
        idx = tc.get("index", 0)
        entry = self.tool_items.setdefault(idx, {
            "id": _new_item_id("fc"),
            "call_id": tc.get("id") or _new_item_id("call"),
            "name": "",
            "arguments": "",
            "announced": False,
        })
        if tc.get("id"):
            entry["call_id"] = tc["id"]
        fn = tc.get("function") or {}
        if fn.get("name"):
            entry["name"] = fn["name"]
        if fn.get("arguments"):
            entry["arguments"] += fn["arguments"]

        if not entry["announced"] and entry["name"]:
            entry["announced"] = True
            events.append(_sse_event("response.output_item.added", {
                "output_index": idx + 1,
                "item": {
                    "type": "function_call",
                    "id": entry["id"],
                    "call_id": entry["call_id"],
                    "name": entry["name"],
                    "status": "in_progress",
                },
            }))
        if fn.get("arguments"):
            events.append(_sse_event("response.function_call_arguments.delta", {
                "item_id": entry["id"],
                "output_index": idx + 1,
                "delta": fn["arguments"],
            }))
        return events

    def completion_events(self) -> list[str]:
        events: list[str] = []
        for idx, entry in sorted(self.tool_items.items()):
            events.append(_sse_event("response.output_item.done", {
                "output_index": idx + 1,
                "item": {
                    "type": "function_call",
                    "id": entry["id"],
                    "call_id": entry["call_id"],
                    "name": entry["name"],
                    "arguments": entry["arguments"] or "{}",
                    "status": "completed",
                },
            }))
        if self.text_part_started:
            events.append(_sse_event("response.output_item.done", {
                "output_index": 0,
                "item": {
                    "type": "message",
                    "id": self.message_item_id,
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": ""}],
                },
            }))
        usage = self.usage or {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
        events.append(_sse_event("response.completed", {
            "response": {
                "id": self.response_id,
                "object": "response",
                "status": "completed",
                "created_at": self.created_at,
                "model": self.model,
                "output": [],
                "usage": usage,
                "incomplete_details": None,
            },
        }))
        return events


def parse_chat_sse_line(line: str) -> dict | None:
    line = line.strip()
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    if payload == "[DONE]":
        return {"__done__": True}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


async def transform_chat_sse_stream(
    source: AsyncIterator[bytes | str],
    *,
    model: str = "lima-1.3",
) -> AsyncIterator[str]:
    """Async wrapper: chat completion SSE → Responses API SSE."""
    converter = ResponsesStreamConverter(model=model)
    for ev in converter.bootstrap_events():
        yield ev
    async for raw in source:
        if isinstance(raw, bytes):
            line = raw.decode("utf-8", errors="replace")
        else:
            line = raw
        for part in line.split("\n"):
            chunk = parse_chat_sse_line(part)
            if not chunk:
                continue
            if chunk.get("__done__"):
                for ev in converter.completion_events():
                    yield ev
                return
            for ev in converter.feed_chat_chunk(chunk):
                yield ev
    for ev in converter.completion_events():
        yield ev


def transform_chat_sse_iter(
    lines: Iterator[str],
    *,
    model: str = "lima-1.3",
) -> Iterator[str]:
    """Sync iterator helper for tests."""
    converter = ResponsesStreamConverter(model=model)
    for ev in converter.bootstrap_events():
        yield ev
    for line in lines:
        chunk = parse_chat_sse_line(line)
        if not chunk:
            continue
        if chunk.get("__done__"):
            for ev in converter.completion_events():
                yield ev
            return
        for ev in converter.feed_chat_chunk(chunk):
            yield ev
    for ev in converter.completion_events():
        yield ev
