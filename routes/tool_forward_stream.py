"""Anthropic tool-route streaming (CQ-014 slice 12).

Tier1 now uses real HTTP streaming with on-the-fly
OpenAI SSE → Anthropic SSE conversion for tool calls.
"""

from __future__ import annotations

import json
import uuid
import time

from converters.anthropic_format import (
    convert_messages_anthropic_to_openai,
    convert_tools_anthropic_to_openai,
    inject_anthropic_body_preflight,
    inject_anthropic_context_preflight,
    convert_response_openai_to_anthropic,
)


def prepare_tool_openai_payload(body: dict) -> tuple[list, list, bool]:
    body_size = len(json.dumps(body, ensure_ascii=False))
    skip_tier1 = body_size > 100000
    openai_tools = convert_tools_anthropic_to_openai(body.get("tools", []))
    openai_msgs = convert_messages_anthropic_to_openai(body.get("messages", []))
    inject_anthropic_context_preflight(openai_msgs, body)
    inject_anthropic_body_preflight(body, openai_msgs)
    return openai_tools, openai_msgs, skip_tier1


# ── OpenAI SSE → Anthropic SSE streaming converter ────────────────────────────

class _ToolCallAccumulator:
    """Accumulate OpenAI streaming tool call fragments into complete tool calls."""

    def __init__(self):
        self.calls: dict[int, dict] = {}  # index -> {id, name, arguments}

    def feed(self, tool_calls: list[dict]) -> list[dict]:
        """Feed a delta tool_calls chunk. Returns list of completed tool calls."""
        completed = []
        for tc in tool_calls:
            idx = tc.get("index", 0)
            if idx not in self.calls:
                self.calls[idx] = {
                    "id": tc.get("id", ""),
                    "name": "",
                    "arguments": "",
                }
            entry = self.calls[idx]
            fn = tc.get("function", {})
            if fn.get("name"):
                entry["name"] = fn["name"]
            if fn.get("arguments"):
                entry["arguments"] += fn["arguments"]
        return completed

    def get_all(self) -> list[dict]:
        return [
            {"id": c["id"], "name": c["name"], "arguments": c["arguments"]}
            for c in self.calls.values()
            if c["name"]
        ]


async def _stream_openai_sse_to_anthropic(
    backend_url: str,
    backend_headers: dict,
    req_body: dict,
    msg_id: str,
    model: str,
) -> "AsyncIterator[str]":
    """Stream from an OpenAI-compatible backend and convert to Anthropic SSE."""
    import httpx

    req_body["stream"] = True
    acc = _ToolCallAccumulator()
    text_content = ""
    block_index = 0
    text_block_started = False
    emitted_tool_blocks: set[int] = set()
    finished = False

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST", backend_url, headers=backend_headers, json=req_body,
        ) as resp:
            if resp.status_code != 200:
                body_text = await resp.aread()
                raise RuntimeError(
                    f"Backend returned {resp.status_code}: {str(body_text)[:200]}"
                )

            # Emit message_start
            yield (
                f"event: message_start\n"
                f"data: {json.dumps({'type': 'message_start', 'message': {'id': msg_id, 'type': 'message', 'role': 'assistant', 'model': model, 'content': [], 'stop_reason': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"
            )

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    finished = True
                    break

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                tool_calls = delta.get("tool_calls")

                # Handle text content
                if content:
                    if not text_block_started:
                        text_block_started = True
                        yield (
                            f"event: content_block_start\n"
                            f"data: {json.dumps({'type': 'content_block_start', 'index': block_index, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
                        )
                    text_content += content
                    yield (
                        f"event: content_block_delta\n"
                        f"data: {json.dumps({'type': 'content_block_delta', 'index': block_index, 'delta': {'type': 'text_delta', 'text': content}})}\n\n"
                    )

                # Handle tool calls
                if tool_calls:
                    acc.feed(tool_calls)
                    for tc in tool_calls:
                        idx = tc.get("index", 0)
                        if idx in emitted_tool_blocks:
                            continue
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            # New tool call starting — emit content_block_start
                            emitted_tool_blocks.add(idx)
                            yield (
                                f"event: content_block_start\n"
                                f"data: {json.dumps({'type': 'content_block_start', 'index': block_index, 'content_block': {'type': 'tool_use', 'id': acc.calls[idx]['id'], 'name': fn['name'], 'input': {}}})}\n\n"
                            )
                        args = fn.get("arguments", "")
                        if args:
                            yield (
                                f"event: content_block_delta\n"
                                f"data: {json.dumps({'type': 'content_block_delta', 'index': block_index, 'delta': {'type': 'input_json_delta', 'partial_json': args}})}\n\n"
                            )
                    block_index = len(emitted_tool_blocks) + (1 if text_content else 0)

            # Emit content_block_stop for each block
            final_blocks = 0
            if text_content:
                yield (
                    f"event: content_block_stop\n"
                    f"data: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
                )
                final_blocks += 1
            for i, tc in enumerate(acc.get_all()):
                idx = final_blocks + i
                yield (
                    f"event: content_block_stop\n"
                    f"data: {json.dumps({'type': 'content_block_stop', 'index': idx})}\n\n"
                )

            # Determine stop_reason
            stop_reason = "tool_use" if acc.get_all() else "end_turn"
            yield (
                f"event: message_delta\n"
                f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': stop_reason}, 'usage': {'input_tokens': 0, 'output_tokens': 0}})}\n\n"
            )
            yield (
                f"event: message_stop\n"
                f"data: {json.dumps({'type': 'message_stop'})}\n\n"
            )


async def stream_tier1_openai(body: dict, openai_tools: list, openai_msgs: list, deps: dict):
    """Real streaming: OpenAI SSE → Anthropic SSE conversion on-the-fly."""
    import asyncio

    backends = deps["iter_tool_backends"](deps["TOOL_TIER1_BACKENDS"])
    BACKENDS = deps["BACKENDS"]
    _ht = deps["health_tracker"]

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    for name in backends:
        backend = BACKENDS[name]
        req_body = {
            "model": backend["model"],
            "messages": openai_msgs,
            "tools": openai_tools,
            "max_tokens": body.get("max_tokens", 4096),
            "tool_choice": "auto",
        }
        if name.startswith("aliyun"):
            req_body["enable_thinking"] = False

        backend_headers = {"Content-Type": "application/json"}
        key = backend.get("key", "")
        if key and key not in ("none", ""):
            backend_headers["Authorization"] = f"Bearer {key}"

        t0 = time.time()
        try:
            async for event in _stream_openai_sse_to_anthropic(
                backend["url"], backend_headers, req_body, msg_id, backend["model"],
            ):
                yield event
            _ht.record_success(name, (time.time() - t0) * 1000)
            return
        except Exception as exc:
            code = getattr(exc, "code", None) or getattr(exc, "status", None) or 500
            _ht.record_failure(name, error_code=code)


async def stream_tier2_native(body: dict, deps: dict):
    import json
    import urllib.request as _ur

    _ht = deps["health_tracker"]
    pick = deps["pick_tool_backend"]
    BACKENDS = deps["BACKENDS"]
    native_backends = deps["ANTHROPIC_NATIVE_BACKENDS"]

    for _attempt in range(2):
        name = pick(native_backends)
        if not name:
            break
        backend = BACKENDS[name]
        fwd = dict(body)
        fwd["model"] = backend["model"]
        fwd["stream"] = True
        payload = json.dumps(fwd, ensure_ascii=False).encode()
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if backend.get("auth") == "bearer":
            headers["Authorization"] = f"Bearer {backend['key']}"
        else:
            headers["x-api-key"] = backend["key"]
        try:
            req = _ur.Request(backend["url"], data=payload, headers=headers)
            resp = _ur.urlopen(req, timeout=60)
            _ht.record_success(name, 0)
            buf = b""
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        yield decoded + "\n\n"
            if buf.strip():
                yield buf.decode("utf-8", errors="replace").strip() + "\n\n"
            resp.close()
            return
        except Exception:
            _ht.record_failure(name, error_code=None)


async def anthropic_native_stream(body: dict, deps: dict):
    """Tier1 OpenAI tool stream → Tier2 Anthropic-native passthrough."""
    openai_tools, openai_msgs, skip_tier1 = prepare_tool_openai_payload(body)
    if not skip_tier1:
        tier1_sent = False
        async for chunk in stream_tier1_openai(body, openai_tools, openai_msgs, deps):
            tier1_sent = True
            yield chunk
        if tier1_sent:
            return
    async for chunk in stream_tier2_native(body, deps):
        yield chunk
        return
    yield (
        'event: error\ndata: {"type":"error","error":{"message":"All backends exhausted"}}\n\n'
    )
