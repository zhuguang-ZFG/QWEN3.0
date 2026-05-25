"""server.py — LiMa（力码）OpenAI 兼容接口层
让 Cursor、Claude Code、VS Code Copilot 等 AI IDE 直接接入。
支持流式/非流式 ChatCompletion，兼容 OpenAI API 格式。
"""
import sys, os, json, time, asyncio, threading, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from chat_models import ChatRequest, Message, extract_system_prompt
import smart_router
from vision_handler import (
    _vision_route, _stream_vision_response,
)
from converters.anthropic_format import (
    convert_tools_anthropic_to_openai as _convert_tools_anthropic_to_openai,
    convert_messages_anthropic_to_openai as _convert_messages_anthropic_to_openai,
    anthropic_system_text as _anthropic_system_text,
    last_openai_user_text as _last_openai_user_text,
    inject_anthropic_context_preflight as _inject_anthropic_context_preflight,
    anthropic_text_fallback as _anthropic_text_fallback,
    normalize_openai_text as _normalize_openai_text,
    convert_response_openai_to_anthropic as _convert_response_openai_to_anthropic,
)


def _last_resort_call(messages: list) -> str:
    """Nuclear fallback: direct Cloudflare call, bypasses all routing/health logic."""
    import urllib.request, logging
    account_id = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')
    token = os.environ.get('CLOUDFLARE_TOKEN', '')
    if not account_id or not token:
        return ""
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    body = json.dumps({"model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "messages": messages[-5:], "max_tokens": 4096}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logging.warning(f"[LAST_RESORT] Cloudflare fallback failed: {type(e).__name__}")
        return ""

# ── App ─────────────────────────────────────────────────────────────────────
from server_lifespan import lifespan

app = FastAPI(title="LiMa", version="1.3",
              description="LiMa（力码）— 智能编程助手 API，OpenAI 兼容",
              lifespan=lifespan)

MAX_BODY_SIZE = 2 * 1024 * 1024  # 2MB (coding assistant 上下文可能较大)

@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_SIZE:
                return JSONResponse(status_code=413, content={"error": {"message": "Request body too large"}})
        except ValueError:
            return JSONResponse(status_code=400, content={"error": {"message": "Invalid Content-Length"}})
    return await call_next(request)

MODEL_ID = "lima-1.3"
MODEL_CREATED = int(time.time())

# ── 统计收集器 ─────────────────────────────────────────────────────────────────
_stats_lock = threading.Lock()
_stats = {
    "total_requests": 0,
    "backend_calls": {},
    "intent_distribution": {},
    "recent_logs": [],
    "start_time": time.time(),
}
app.state.stats = _stats

# 后端启用/禁用状态
_backend_enabled = {}
_loaded_modules: dict = {}

# ── Request Tracking (extracted to routes/request_tracking.py) ────────────────
import routes.request_tracking as _rt_mod
_rt_mod.inject_state(_stats, _stats_lock)
_record_fallback = _rt_mod.record_fallback
_record_request = _rt_mod.record_request
_get_ip_location = _rt_mod.get_ip_location
_client_ip = _rt_mod.client_ip
_detect_ide = _rt_mod.detect_ide
_elapsed_ms = _rt_mod.elapsed_ms
FALLBACK_LOG = _rt_mod.FALLBACK_LOG

# ── Tool Call Forwarding (extracted to routes/tool_forward.py) ─────────────────
import urllib.parse as _urllib_parse
import routes.tool_forward as _tool_fwd
_tool_fwd.inject_state(_record_request, MODEL_ID)
_anthropic_native_forward = _tool_fwd.anthropic_native_forward
_anthropic_native_stream = _tool_fwd.anthropic_native_stream
_simulate_anthropic_sse = _tool_fwd.simulate_anthropic_sse
_tool_call_forward = _tool_fwd.tool_call_forward
_tool_call_stream = _tool_fwd.tool_call_stream
_pick_tool_backend = _tool_fwd.pick_tool_backend
_iter_tool_backends = _tool_fwd.iter_tool_backends
TOOL_TIER1_BACKENDS = _tool_fwd.TOOL_TIER1_BACKENDS
ANTHROPIC_NATIVE_BACKENDS = _tool_fwd.ANTHROPIC_NATIVE_BACKENDS


from routes.images import build_pollinations_url as _build_pollinations_url

# ── Chat handler (extracted to routes/chat_handler.py) ───────────────────────
from routes.chat_handler import handle_chat as _handle_chat, inject_deps as _inject_chat_handler_deps
from routes.chat_stream import inject_deps as _inject_chat_stream_deps
from routes.chat_support import log_sys_prompt as _log_sys_prompt, thinking_route as _thinking_route

_inject_chat_handler_deps(
    model_id=MODEL_ID,
    record_request=_record_request,
    record_fallback=_record_fallback,
    build_pollinations_url=_build_pollinations_url,
)
_inject_chat_stream_deps(
    last_resort_call=_last_resort_call,
    build_pollinations_url=_build_pollinations_url,
)

# ── Anthropic streaming (extracted to routes/anthropic_stream.py) ────────────
from routes.anthropic_stream import (
    anthropic_stream as _anthropic_stream,
    anthropic_stream_passthrough as _anthropic_stream_passthrough,
    inject_deps as _inject_anthropic_stream_deps,
)
_inject_anthropic_stream_deps(
    last_resort_call=_last_resort_call,
    thinking_route=_thinking_route,
    record_request=_record_request,
    extract_system_prompt=extract_system_prompt,
    log_sys_prompt=_log_sys_prompt,
)


# ── Route registration (extracted to routes/route_registry.py) ───────────────
from routes.route_registry import RouteRegistryDeps, register_all_routes

_registered = register_all_routes(
    app,
    RouteRegistryDeps(
        model_id=MODEL_ID,
        model_created=MODEL_CREATED,
        stats=_stats,
        stats_lock=_stats_lock,
        backend_enabled=_backend_enabled,
        loaded_modules=_loaded_modules,
        client_ip=lambda request: _client_ip(request),
        detect_ide=lambda messages: _detect_ide(messages),
        elapsed_ms=lambda started_at: _elapsed_ms(started_at),
        vision_route=lambda messages, max_tokens=4096, ide="unknown": _vision_route(messages, max_tokens, ide),
        stream_vision_response=lambda chat_id, content: _stream_vision_response(chat_id, content),
        record_request=lambda *args, **kwargs: _record_request(*args, **kwargs),
        anthropic_native_stream=lambda body: _anthropic_native_stream(body),
        anthropic_native_forward=lambda body: _anthropic_native_forward(body),
        anthropic_stream=lambda *args, **kwargs: _anthropic_stream(*args, **kwargs),
        anthropic_stream_passthrough=lambda body, model: _anthropic_stream_passthrough(body, model),
        handle_chat=lambda *args, **kwargs: _handle_chat(*args, **kwargs),
    ),
)
chat_completions = _registered.chat_completions
anthropic_messages = _registered.anthropic_messages
list_models = _registered.list_models
health = _registered.health
live_key = _registered.live_key
router_status = _registered.router_status

# ── Startup ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print('[LiMa] Warming up router model...', file=sys.stderr)
    smart_router.warmup_router_model()
    uvicorn.run(app, host="0.0.0.0", port=8080)
