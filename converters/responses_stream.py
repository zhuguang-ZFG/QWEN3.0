"""SSE conversion helpers for the OpenAI Responses API shim."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator


def _new_response_id() -> str:
    return f"resp_{uuid.uuid4().hex[:24]}"


def _new_item_id(prefix: str = "msg") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _sse_event(event_type: str, payload: dict) -> str:
    payload = dict(payload)
    payload.setdefault("type", event_type)
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ResponsesStreamConverter:
    def __init__(self, *, model: str = "lima-1.3") -> None:
        self.response_id = _new_response_id()
        self.model = model
        self.created_at = int(time.time())
        self.message_item_id = _new_item_id("msg")
        self.text_part_started = False
        self.message_output_index: int | None = None
        self.reasoning_item_id = _new_item_id("rs")
        self.reasoning_output_index: int | None = None
        self.reasoning_started = False
        self.reasoning_text = ""
        self.tool_items: dict[int, dict] = {}
        self.next_output_index = 0
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
        self.message_output_index = self._allocate_output_index()
        return [
            _sse_event("response.output_item.added", {
                "output_index": self.message_output_index,
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
                "output_index": self.message_output_index,
                "content_index": 0,
                "part": {"type": "output_text", "text": ""},
            }),
        ]

    def _allocate_output_index(self) -> int:
        output_index = self.next_output_index
        self.next_output_index += 1
        return output_index

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
            delta = choice.get("delta") or {}
            reasoning_delta = _reasoning_delta(delta)
            if reasoning_delta:
                events.extend(self._feed_reasoning_delta(reasoning_delta))
            if delta.get("content"):
                events.extend(self._ensure_message_item())
                events.append(_sse_event("response.output_text.delta", {
                    "item_id": self.message_item_id,
                    "output_index": self.message_output_index,
                    "content_index": 0,
                    "delta": delta["content"],
                }))
            for tc in delta.get("tool_calls") or []:
                events.extend(self._feed_tool_delta(tc))
        return events

    def _feed_reasoning_delta(self, text: str) -> list[str]:
        events = self._ensure_reasoning_item()
        self.reasoning_text += text
        events.append(_sse_event("response.reasoning_summary_text.delta", {
            "item_id": self.reasoning_item_id,
            "output_index": self.reasoning_output_index,
            "summary_index": 0,
            "delta": text,
        }))
        return events

    def _ensure_reasoning_item(self) -> list[str]:
        if self.reasoning_started:
            return []
        self.reasoning_started = True
        self.reasoning_output_index = self._allocate_output_index()
        return [
            _sse_event("response.output_item.added", {
                "output_index": self.reasoning_output_index,
                "item": {
                    "type": "reasoning",
                    "id": self.reasoning_item_id,
                    "status": "in_progress",
                    "summary": [],
                    "encrypted_content": None,
                },
            }),
            _sse_event("response.reasoning_summary_part.added", {
                "item_id": self.reasoning_item_id,
                "output_index": self.reasoning_output_index,
                "summary_index": 0,
                "part": {"type": "summary_text", "text": ""},
            }),
        ]

    def _feed_tool_delta(self, tc: dict) -> list[str]:
        events: list[str] = []
        idx = tc.get("index", 0)
        entry = self.tool_items.setdefault(idx, {
            "id": _new_item_id("fc"),
            "call_id": tc.get("id") or _new_item_id("call"),
            "name": "",
            "arguments": "",
            "announced": False,
            "output_index": None,
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
            entry["output_index"] = self._allocate_output_index()
            events.append(_sse_event("response.output_item.added", {
                "output_index": entry["output_index"],
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
                "output_index": entry["output_index"],
                "delta": fn["arguments"],
            }))
        return events

    def completion_events(self) -> list[str]:
        events: list[str] = []
        if self.reasoning_started:
            events.extend(self._complete_reasoning_item())
        for _idx, entry in sorted(self.tool_items.items()):
            events.append(_sse_event("response.output_item.done", {
                "output_index": entry["output_index"],
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
                "output_index": self.message_output_index,
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

    def _complete_reasoning_item(self) -> list[str]:
        summary = [{"type": "summary_text", "text": self.reasoning_text}]
        return [
            _sse_event("response.reasoning_summary_part.done", {
                "item_id": self.reasoning_item_id,
                "output_index": self.reasoning_output_index,
                "summary_index": 0,
                "part": summary[0],
            }),
            _sse_event("response.output_item.done", {
                "output_index": self.reasoning_output_index,
                "item": {
                    "type": "reasoning",
                    "id": self.reasoning_item_id,
                    "status": "completed",
                    "summary": summary,
                    "encrypted_content": None,
                },
            }),
        ]


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


def _reasoning_delta(delta: dict) -> str:
    for key in ("reasoning_content", "reasoning", "reasoning_text"):
        value = delta.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


async def transform_chat_sse_stream(
    source: AsyncIterator[bytes | str],
    *,
    model: str = "lima-1.3",
) -> AsyncIterator[str]:
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
