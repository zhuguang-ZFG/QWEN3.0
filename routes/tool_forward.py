"""routes/tool_forward.py — Anthropic tool-call forwarding infrastructure.

Handles tool_use requests from Claude Code / IDE clients:
- Tier 1: OpenAI-compatible backends (fast, format-converted)
- Tier 2: LongCat Anthropic-native backends (fallback)
- OpenRouter DeepSeek R1 (legacy direct forward)
"""

import asyncio
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx as _httpx

from converters.anthropic_format import (
    convert_messages_anthropic_to_openai,
    convert_response_openai_to_anthropic,
    convert_tool_choice_anthropic_to_openai,
    convert_tools_anthropic_to_openai,
    inject_anthropic_body_preflight,
    inject_anthropic_context_preflight,
)

TOOL_BACKEND_URL = "https://openrouter.ai/api/v1/chat/completions"
TOOL_BACKEND_MODEL = "deepseek/deepseek-v4-flash:free"
TOOL_BACKEND_KEY = os.environ.get("OPENROUTER_API_KEY", "")

ANTHROPIC_NATIVE_BACKENDS = [
    'longcat_chat', 'longcat',
    # M6: deepseek_free deleted; longcat_lite/thinking/omni offline 2026-05-29
]

# Tier1 skip threshold: configurable via LIMA_TOOL_BODY_LIMIT (bytes), default 512KB
_TOOL_BODY_LIMIT = int(os.environ.get("LIMA_TOOL_BODY_LIMIT", "524288"))

TOOL_TIER1_BACKENDS: list[str] = []


def _refresh_tool_tiers() -> None:
    """Dynamically discover tool-call-capable backends from registry."""
    import importlib
    try:
        reg = importlib.import_module("backends_registry")
        runtime_topology = importlib.import_module("runtime_topology")
    except ImportError:
        return
    tier1 = []
    for name, cfg in getattr(reg, "BACKENDS", {}).items():
        if runtime_topology.is_host_dependent_backend(name):
            continue
        caps = set(cfg.get("caps", []))
        if "tool_calls" not in caps:
            continue
        if cfg.get("fmt") == "anthropic":
            if name not in ANTHROPIC_NATIVE_BACKENDS:
                ANTHROPIC_NATIVE_BACKENDS.append(name)
        elif cfg.get("fmt") == "openai":
            tier1.append(name)
    # Sort: prefer backends with keys, then by timeout
    tier1.sort(key=lambda n: (
        0 if reg.BACKENDS.get(n, {}).get("key", "") not in ("", "none", "YOUR_KEY_HERE") else 1,
        reg.BACKENDS.get(n, {}).get("timeout", 30),
    ))
    TOOL_TIER1_BACKENDS[:] = tier1


_refresh_tool_tiers()

_record_request_fn = None
_model_id = "lima-1.3"


def inject_state(record_fn, model_id: str):
    global _record_request_fn, _model_id
    _record_request_fn = record_fn
    _model_id = model_id


def _tool_backend_selectable(name: str) -> bool:
    """Configured, healthy tool backends suitable for IDE tool forwarding."""
    import health_tracker as _ht
    import route_scorer as _rs
    from backends import BACKENDS

    if not BACKENDS.get(name, {}).get("key"):
        return False
    if _ht.is_cooled_down(name):
        return False
    state = _ht.get_backend_state(name)
    return _rs.is_selectable(name, "ide", state)


def pick_tool_backend(tier: list):
    """从候选列表中按声明顺序选第一个健康后端。"""
    for n in tier:
        if _tool_backend_selectable(n):
            return n
    return None


def iter_tool_backends(tier: list):
    """Yield configured, non-cooled tool backends once per request."""
    for n in tier:
        if _tool_backend_selectable(n):
            yield n


async def anthropic_native_forward(body: dict) -> dict:
    """分层 tool 路由：第一梯队 OpenAI 格式(快) → 第二梯队 LongCat 原生(兜底)。"""
    return await asyncio.to_thread(anthropic_native_forward_sync, body)


def anthropic_native_forward_sync(body: dict) -> dict:
    """同步版本，在线程池中执行。"""
    import health_tracker as _ht
    from backends import BACKENDS
    from http_caller import BackendError, call_raw

    body_size = len(json.dumps(body, ensure_ascii=False))
    skip_tier1 = body_size > _TOOL_BODY_LIMIT

    openai_tools = convert_tools_anthropic_to_openai(body.get("tools", []))
    openai_msgs = convert_messages_anthropic_to_openai(body.get("messages", []))
    inject_anthropic_context_preflight(openai_msgs, body)
    inject_anthropic_body_preflight(body, openai_msgs)
    client_tool_choice = convert_tool_choice_anthropic_to_openai(body.get("tool_choice"))

    if not skip_tier1:
        for name in iter_tool_backends(TOOL_TIER1_BACKENDS):
            b = BACKENDS[name]
            msgs = list(openai_msgs)
            # Inject JSON tool prompt for backends that output tools as text.
            # Include actual tool definitions so models that don't understand
            # the OpenAI tools field can still pick the right tool.
            if name in _TEXT_TOOL_BACKENDS:
                prompt = _build_tool_system_prompt(openai_tools)
                msgs.insert(0, {"role": "system", "content": prompt})
            req_body = {"model": b["model"], "messages": msgs,
                "tools": openai_tools, "max_tokens": body.get("max_tokens", 4096),
                "tool_choice": client_tool_choice}
            if name.startswith("aliyun"):
                req_body["enable_thinking"] = False
            payload = json.dumps(req_body, ensure_ascii=False).encode()
            try:
                data = call_raw(name, payload)
                # Text→tool extraction for backends that output JSON-as-text
                if name in _TEXT_TOOL_BACKENDS:
                    data = _extract_text_tools_from_response(data)
                return convert_response_openai_to_anthropic(data, b["model"])
            except BackendError as exc:
                _ht.record_failure(name, error_code=exc.status_code)
                continue
            except Exception as exc:
                code = getattr(exc, "code", None) or getattr(exc, "status", None) or 500
                _ht.record_failure(name, error_code=code)
                continue

    # Tier 2: LongCat Anthropic native
    import urllib.request as _ur
    for _attempt in range(2):
        name = pick_tool_backend(ANTHROPIC_NATIVE_BACKENDS)
        if not name:
            break
        b = BACKENDS[name]
        
        # Validate API key before making request
        if not b.get("key"):
            _ht.record_failure(name, error_code=500)
            import logging
            logging.warning("tool_forward: backend %s has no API key configured, skipping", name)
            continue
        
        fwd = dict(body)
        fwd["model"] = b["model"]
        payload = json.dumps(fwd, ensure_ascii=False).encode()
        try:
            headers = {"Content-Type": "application/json",
                       "anthropic-version": "2023-06-01"}
            if b.get("auth") == "bearer":
                headers["Authorization"] = f"Bearer {b['key']}"
            else:
                headers["x-api-key"] = b["key"]
            req = _ur.Request(b["url"], data=payload, headers=headers)
            with _ur.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            _ht.record_success(name, 0)
            return data
        except Exception as e:
            code = getattr(e, 'code', None) or getattr(e, 'status', None) or 500
            _ht.record_failure(name, error_code=code)
            continue

    return {"type": "error", "error": {"type": "api_error",
            "message": "All tool backends exhausted"}}


def _stream_deps() -> dict:
    import health_tracker as _ht
    from backends import BACKENDS

    return {
        "BACKENDS": BACKENDS,
        "health_tracker": _ht,
        "iter_tool_backends": iter_tool_backends,
        "pick_tool_backend": pick_tool_backend,
        "TOOL_TIER1_BACKENDS": TOOL_TIER1_BACKENDS,
        "ANTHROPIC_NATIVE_BACKENDS": ANTHROPIC_NATIVE_BACKENDS,
        "simulate_anthropic_sse": simulate_anthropic_sse,
    }


async def anthropic_native_stream(body: dict):
    """分层 tool 流式路由：第一梯队 OpenAI(快) → 第二梯队 LongCat(兜底)。"""
    from routes.tool_forward_stream import anthropic_native_stream as _stream

    async for chunk in _stream(body, _stream_deps()):
        yield chunk


def simulate_anthropic_sse(result: dict):
    """把完整的 Anthropic 响应转为 SSE 事件流。"""
    msg_id = result.get("id", "msg_" + uuid.uuid4().hex[:12])
    model = result.get("model", "lima-1.3")
    yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'usage':{'input_tokens':0,'output_tokens':0}}})}\n\n"
    for i, block in enumerate(result.get("content", [])):
        if block.get("type") == "text":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'text','text':''}})}\n\n"
            text = block.get("text", "")
            for j in range(0, len(text), 40):
                yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'text_delta','text':text[j:j+40]}}, ensure_ascii=False)}\n\n"
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"
        elif block.get("type") == "tool_use":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'tool_use','id':block['id'],'name':block['name'],'input':{}}})}\n\n"
            yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'input_json_delta','partial_json':json.dumps(block.get('input',{}), ensure_ascii=False)}})}\n\n"
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"
    stop_reason = result.get("stop_reason", "end_turn")
    yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':stop_reason},'usage':result.get('usage',{})})}\n\n"
    yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"


async def tool_call_forward(body: dict) -> dict:
    """Forward tool call request via OpenRouter."""
    openai_tools = convert_tools_anthropic_to_openai(body["tools"])
    openai_messages = convert_messages_anthropic_to_openai(body["messages"])
    inject_anthropic_context_preflight(openai_messages, body)
    inject_anthropic_body_preflight(body, openai_messages)

    payload = {
        "model": TOOL_BACKEND_MODEL,
        "messages": openai_messages,
        "tools": openai_tools,
        "max_tokens": body.get("max_tokens", 4096),
    }

    t0 = time.time()
    try:
        async with _httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                TOOL_BACKEND_URL,
                headers={
                    "Authorization": f"Bearer {TOOL_BACKEND_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            openai_resp = resp.json()
    except Exception as e:
        return {
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message", "role": "assistant",
            "model": body.get("model", _model_id),
            "content": [{"type": "text", "text": f"[Tool backend error: {e}]"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    duration_ms = int((time.time() - t0) * 1000)
    if _record_request_fn:
        _record_request_fn("tool_call", TOOL_BACKEND_MODEL, "tool_use", duration_ms, True)

    if "error" in openai_resp:
        err_msg = openai_resp["error"].get("message", str(openai_resp["error"]))
        return {
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message", "role": "assistant",
            "model": body.get("model", _model_id),
            "content": [{"type": "text", "text": f"[Tool backend error: {err_msg}]"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    return convert_response_openai_to_anthropic(
        openai_resp, body.get("model", _model_id)
    )


async def tool_call_stream(body: dict):
    """Tool call streaming response (waits for full response, then simulates SSE)."""
    result = await tool_call_forward(body)
    msg_id = result["id"]
    model = result["model"]

    yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':0,'output_tokens':0}}})}\n\n"

    for i, block in enumerate(result.get("content", [])):
        if block["type"] == "text":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'text','text':''}})}\n\n"
            text = block["text"]
            for j in range(0, len(text), 40):
                chunk = text[j:j+40]
                yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"
        elif block["type"] == "tool_use":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'tool_use','id':block['id'],'name':block['name'],'input':{}}})}\n\n"
            input_json = json.dumps(block["input"], ensure_ascii=False)
            yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'input_json_delta','partial_json':input_json}})}\n\n"
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"

    stop_reason = result.get("stop_reason", "end_turn")
    usage = result.get("usage", {"input_tokens": 0, "output_tokens": 0})
    yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':stop_reason,'stop_sequence':None},'usage':usage})}\n\n"
    yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"


# ── Text → Tool Call Extraction ───────────────────────────────────────────────

from text_tool_extractor import (
    TEXT_TOOL_BACKENDS as _TEXT_TOOL_BACKENDS,
)
from text_tool_extractor import (
    TEXT_TOOL_SYSTEM_PROMPT as _TEXT_TOOL_SYSTEM_PROMPT,
)
from text_tool_extractor import (
    build_tool_system_prompt as _build_tool_system_prompt,
)
from text_tool_extractor import (
    extract_tool_calls_from_text as _extract_tool_calls_from_text,
)


def _extract_text_tools_from_response(data: dict) -> dict:
    """Extract tool calls from text content in OpenAI API response.

    Delegates to text_tool_extractor.extract_tool_calls_from_text for parsing.
    """
    choices = data.get("choices", [])
    if not choices:
        return data

    message = choices[0].get("message", {})
    if message.get("tool_calls"):
        return data  # Already has proper tool_calls

    content = message.get("content", "") or ""
    if not content:
        return data

    cleaned, tool_calls = _extract_tool_calls_from_text(content)
    if tool_calls:
        message["tool_calls"] = tool_calls
        message["content"] = cleaned or None
        choices[0]["finish_reason"] = "tool_calls"

    return data
