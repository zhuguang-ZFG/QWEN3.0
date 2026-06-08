"""SSE conversion helpers for the OpenAI Responses API shim."""

from __future__ import annotations

import json
import time
import uuid

from converters.responses_errors import chat_error_from_chunk, failed_response_payload
from converters.responses_response_fields import with_response_fields
from converters.responses_stream_items import (
    completed_message_item,
    completed_reasoning_item,
    completed_tool_item,
    incomplete_reason,
)
from converters.responses_stream_parse import reasoning_delta
from converters.responses_usage import chat_usage_to_responses_usage


def _new_response_id() -> str:
    return f"resp_{uuid.uuid4().hex[:24]}"


def _new_item_id(prefix: str = "msg") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _sse_event(event_type: str, payload: dict) -> str:
    payload = dict(payload)
    payload.setdefault("type", event_type)
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ResponsesStreamConverter:
    def __init__(
        self,
        *,
        model: str = "lima-1.3",
        response_fields: dict | None = None,
    ) -> None:
        self.response_id = _new_response_id()
        self.model = model
        self.created_at = int(time.time())
        self.response_fields = dict(response_fields or {})
        self.message_item_id = _new_item_id("msg")
        self.text_part_started = False
        self.text_content = ""
        self.message_output_index: int | None = None
        self.reasoning_item_id = _new_item_id("rs")
        self.reasoning_output_index: int | None = None
        self.reasoning_started = False
        self.reasoning_text = ""
        self.tool_items: dict[int, dict] = {}
        self.next_output_index = 0
        self.usage: dict | None = None
        self.failed = False
        self.finish_reason = ""

    def bootstrap_events(self) -> list[str]:
        return [
            _sse_event("response.created", {
                "response": self._response_payload(
                    status="in_progress",
                    output=[],
                    usage=None,
                    incomplete_details=None,
                ),
            }),
            _sse_event("response.in_progress", {
                "response": self._response_payload(status="in_progress"),
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
        error = chat_error_from_chunk(chunk)
        if error:
            self.failed = True
            payload = failed_response_payload(
                response_id=self.response_id,
                created_at=self.created_at,
                model=self.model,
                usage=self._usage(),
                error=error,
            )
            response = with_response_fields(payload, self.response_fields)
            response.setdefault("parallel_tool_calls", True)
            return [_sse_event("response.failed", {
                "response": response,
            })]
        if chunk.get("model"):
            self.model = chunk["model"]
        if chunk.get("usage"):
            self.usage = chat_usage_to_responses_usage(chunk["usage"])

        for choice in chunk.get("choices") or []:
            if choice.get("finish_reason") and not self.finish_reason:
                self.finish_reason = choice["finish_reason"]
            delta = choice.get("delta") or {}
            reasoning = reasoning_delta(delta)
            if reasoning:
                events.extend(self._feed_reasoning_delta(reasoning))
            if delta.get("content"):
                self.text_content += delta["content"]
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
        if fn.get("arguments") and entry["announced"]:
            events.append(_sse_event("response.function_call_arguments.delta", {
                "item_id": entry["id"],
                "output_index": entry["output_index"],
                "delta": fn["arguments"],
            }))
        return events

    def completion_events(self) -> list[str]:
        if self.failed:
            return []
        events: list[str] = []
        output_items: list[dict] = []
        if self.reasoning_started:
            events.extend(self._complete_reasoning_item())
            output_items.append(
                completed_reasoning_item(self.reasoning_item_id, self.reasoning_text)
            )
        for _idx, entry in sorted(self.tool_items.items()):
            if not entry["announced"]:
                continue
            item = completed_tool_item(entry)
            output_items.append(item)
            events.append(_sse_event("response.output_item.done", {
                "output_index": entry["output_index"],
                "item": item,
            }))
        if self.text_part_started:
            item = completed_message_item(self.message_item_id, self.text_content)
            output_items.append(item)
            events.append(_sse_event("response.output_item.done", {
                "output_index": self.message_output_index,
                "item": item,
            }))
        usage = self._usage()
        incomplete_details = self._incomplete_details()
        terminal_event = "response.incomplete" if incomplete_details else "response.completed"
        status = "incomplete" if incomplete_details else "completed"
        events.append(_sse_event(terminal_event, {
            "response": self._response_payload(
                status=status,
                output=output_items,
                usage=usage,
                incomplete_details=incomplete_details,
            ),
        }))
        return events

    def _response_payload(self, *, status: str, **extra: object) -> dict:
        payload = {
            "id": self.response_id,
            "object": "response",
            "status": status,
            "created_at": self.created_at,
            "model": self.model,
            **extra,
        }
        payload = with_response_fields(payload, self.response_fields)
        payload.setdefault("parallel_tool_calls", True)
        return payload

    def _usage(self) -> dict:
        return self.usage or {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def _incomplete_details(self) -> dict | None:
        reason = incomplete_reason(self.finish_reason)
        return {"reason": reason} if reason else None

    def _complete_reasoning_item(self) -> list[str]:
        item = completed_reasoning_item(self.reasoning_item_id, self.reasoning_text)
        return [
            _sse_event("response.reasoning_summary_part.done", {
                "item_id": self.reasoning_item_id,
                "output_index": self.reasoning_output_index,
                "summary_index": 0,
                "part": item["summary"][0],
            }),
            _sse_event("response.output_item.done", {
                "output_index": self.reasoning_output_index,
                "item": item,
            }),
        ]
