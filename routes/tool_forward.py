"""routes/tool_forward.py — Anthropic tool-call forwarding infrastructure.

Handles tool_use requests from Claude Code / IDE clients:
- Tier 1: OpenAI-compatible backends (fast, format-converted)
- Tier 2: LongCat Anthropic-native backends (fallback)
- OpenRouter DeepSeek R1 (legacy direct forward)
"""

import os
import sys
import json
import time
import uuid
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx as _httpx
from converters.anthropic_format import (
    convert_tools_anthropic_to_openai,
    convert_messages_anthropic_to_openai,
    inject_anthropic_body_preflight,
    inject_anthropic_context_preflight,
    convert_response_openai_to_anthropic,
)

TOOL_BACKEND_URL = "https://openrouter.ai/api/v1/chat/completions"
TOOL_BACKEND_MODEL = "deepseek/deepseek-v4-flash:free"
TOOL_BACKEND_KEY = os.environ.get("OPENROUTER_API_KEY", "")

ANTHROPIC_NATIVE_BACKENDS = [
    'longcat_chat', 'longcat', 'deepseek_free',
    'longcat_lite', 'longcat_thinking', 'longcat_omni',
]

TOOL_TIER1_BACKENDS = [
    'groq_gptoss_20b', 'cerebras_gptoss', 'groq_gptoss',
    'github_gpt4o_mini', 'github_gpt4o',
    'mistral_small', 'mistral_devstral', 'mistral_large',
    'scnet_large_ds_flash',
]

_record_request_fn = None
_model_id = "lima-1.3"


def inject_state(record_fn, model_id: str):
    global _record_request_fn, _model_id
    _record_request_fn = record_fn
    _model_id = model_id


def _tool_backend_selectable(name: str) -> bool:
    """Configured, healthy tool backends suitable for IDE tool forwarding."""
    import health_tracker as _ht
    from backends import BACKENDS
    import route_scorer as _rs

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
    from http_caller import call_raw, BackendError
    from backends import BACKENDS
    import health_tracker as _ht

    body_size = len(json.dumps(body, ensure_ascii=False))
    skip_tier1 = body_size > 100000

    openai_tools = convert_tools_anthropic_to_openai(body.get("tools", []))
    openai_msgs = convert_messages_anthropic_to_openai(body.get("messages", []))
    inject_anthropic_context_preflight(openai_msgs, body)
    inject_anthropic_body_preflight(body, openai_msgs)

    if not skip_tier1:
        for name in iter_tool_backends(TOOL_TIER1_BACKENDS):
            b = BACKENDS[name]
            req_body = {"model": b["model"], "messages": openai_msgs,
                "tools": openai_tools, "max_tokens": body.get("max_tokens", 4096),
                "tool_choice": "auto"}
            if name.startswith("aliyun"):
                req_body["enable_thinking"] = False
            payload = json.dumps(req_body, ensure_ascii=False).encode()
            try:
                data = call_raw(name, payload)
                return convert_response_openai_to_anthropic(data, b["model"])
            except BackendError:
                continue

    # Tier 2: LongCat Anthropic native
    import urllib.request as _ur
    for _attempt in range(2):
        name = pick_tool_backend(ANTHROPIC_NATIVE_BACKENDS)
        if not name:
            break
        b = BACKENDS[name]
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


async def anthropic_native_stream(body: dict):
    """分层 tool 流式路由：第一梯队 OpenAI(快) → 第二梯队 LongCat(兜底)。"""
    from http_caller import call_raw, BackendError
    from backends import BACKENDS
    import health_tracker as _ht

    body_size = len(json.dumps(body, ensure_ascii=False))
    skip_tier1 = body_size > 100000

    openai_tools = convert_tools_anthropic_to_openai(body.get("tools", []))
    openai_msgs = convert_messages_anthropic_to_openai(body.get("messages", []))
    inject_anthropic_context_preflight(openai_msgs, body)
    inject_anthropic_body_preflight(body, openai_msgs)

    if not skip_tier1:
        for name in iter_tool_backends(TOOL_TIER1_BACKENDS):
            b = BACKENDS[name]
            req_body = {"model": b["model"], "messages": openai_msgs,
                "tools": openai_tools, "max_tokens": body.get("max_tokens", 4096),
                "tool_choice": "auto"}
            if name.startswith("aliyun"):
                req_body["enable_thinking"] = False
            payload = json.dumps(req_body, ensure_ascii=False).encode()
            try:
                data = await asyncio.to_thread(call_raw, name, payload)
                result = convert_response_openai_to_anthropic(data, b["model"])
                for chunk in simulate_anthropic_sse(result):
                    yield chunk
                return
            except BackendError as e:
                _ht.record_failure(name, error_code=e.status_code)
                continue
            except Exception as e:
                code = getattr(e, 'code', None) or getattr(e, 'status', None) or 500
                _ht.record_failure(name, error_code=code)
                continue

    # Tier 2: LongCat Anthropic native stream
    import urllib.request as _ur
    for _attempt in range(2):
        name = pick_tool_backend(ANTHROPIC_NATIVE_BACKENDS)
        if not name:
            break
        b = BACKENDS[name]
        fwd = dict(body)
        fwd["model"] = b["model"]
        fwd["stream"] = True
        payload = json.dumps(fwd, ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json",
                   "anthropic-version": "2023-06-01"}
        if b.get("auth") == "bearer":
            headers["Authorization"] = f"Bearer {b['key']}"
        else:
            headers["x-api-key"] = b["key"]
        try:
            req = _ur.Request(b["url"], data=payload, headers=headers)
            resp = _ur.urlopen(req, timeout=60)
            _ht.record_success(name, 0)
            buf = b''
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    decoded = line.decode('utf-8', errors='replace').strip()
                    if decoded:
                        yield decoded + '\n\n'
            if buf.strip():
                yield buf.decode('utf-8', errors='replace').strip() + '\n\n'
            resp.close()
            return
        except Exception:
            _ht.record_failure(name, error_code=None)
            continue
    yield 'event: error\ndata: {"type":"error","error":{"message":"All backends exhausted"}}\n\n'


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
