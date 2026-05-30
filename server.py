"""server.py — LiMa（力码）OpenAI 兼容接口层
让 Cursor、Claude Code、VS Code Copilot 等 AI IDE 直接接入。
支持流式/非流式 ChatCompletion，兼容 OpenAI API 格式。
"""
import sys, os, time as time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
import uvicorn

from chat_models import ChatRequest as ChatRequest, Message as Message, extract_system_prompt
import smart_router
from vision_handler import (
    _vision_route, _stream_vision_response,
)
from converters.anthropic_format import (
    convert_response_openai_to_anthropic as _convert_response_openai_to_anthropic,  # noqa: F401
)
from http_body_limit import BodySizeLimitMiddleware
from server_bootstrap import (
    MAX_BODY_SIZE,
    MODEL_CREATED,
    MODEL_ID,
    create_runtime_state,
    last_resort_call as _last_resort_call,
)
from server_lifespan import lifespan

app = FastAPI(title="LiMa", version="1.3",
              description="LiMa（力码）— 智能编程助手 API，OpenAI 兼容",
              lifespan=lifespan)

# Sentry error tracking
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        sentry_sdk.init(
            dsn=_sentry_dsn,
            send_default_pii=True,
            enable_logs=True,
            traces_sample_rate=0.1,
            integrations=[FastApiIntegration()],
        )
    except ImportError:
        pass

app.add_middleware(BodySizeLimitMiddleware, max_body_size=MAX_BODY_SIZE)

_stats, _stats_lock, _backend_enabled, _loaded_modules = create_runtime_state()
app.state.stats = _stats

import routes.request_tracking as _rt_mod
_rt_mod.inject_state(_stats, _stats_lock)
_record_fallback = _rt_mod.record_fallback
_record_request = _rt_mod.record_request
_get_ip_location = _rt_mod.get_ip_location
_client_ip = _rt_mod.client_ip
_detect_ide = _rt_mod.detect_ide
_elapsed_ms = _rt_mod.elapsed_ms
FALLBACK_LOG = _rt_mod.FALLBACK_LOG

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

if __name__ == "__main__":
    print('[LiMa] Warming up router model...', file=sys.stderr)
    smart_router.warmup_router_model()
    uvicorn.run(app, host="0.0.0.0", port=8080)
