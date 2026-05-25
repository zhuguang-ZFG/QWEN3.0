"""Anthropic tool-route streaming (CQ-014 slice 12)."""

from __future__ import annotations

import json

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


async def stream_tier1_openai(body: dict, openai_tools: list, openai_msgs: list, deps: dict):
    import asyncio
    from http_caller import call_raw, BackendError

    backends = deps["iter_tool_backends"](deps["TOOL_TIER1_BACKENDS"])
    BACKENDS = deps["BACKENDS"]
    _ht = deps["health_tracker"]
    simulate = deps["simulate_anthropic_sse"]

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
        payload = json.dumps(req_body, ensure_ascii=False).encode()
        try:
            data = await asyncio.to_thread(call_raw, name, payload)
            result = convert_response_openai_to_anthropic(data, backend["model"])
            for chunk in simulate(result):
                yield chunk
            return
        except BackendError as exc:
            _ht.record_failure(name, error_code=exc.status_code)
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
    """Tier1 OpenAI tool stream, then Tier2 Anthropic-native passthrough."""
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
