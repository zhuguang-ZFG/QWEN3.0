"""server.py — LiMa（力码）OpenAI 兼容接口层
让 Cursor、Claude Code、VS Code Copilot 等 AI IDE 直接接入。
支持流式/非流式 ChatCompletion，兼容 OpenAI API 格式。
"""

import logging

_log = logging.getLogger(__name__)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    _log.debug("server: optional module not available", exc_info=True)
import uvicorn
from fastapi import FastAPI

from chat_models import extract_system_prompt
from http_body_limit import BodySizeLimitMiddleware
from local_router import warmup_router_model
from server_bootstrap import (
    MAX_BODY_SIZE,
    MODEL_CREATED,
    MODEL_ID,
    create_runtime_state,
)
from server_bootstrap import (
    last_resort_call as _last_resort_call,
)
from server_lifespan import lifespan
from vision_handler import (
    _stream_vision_response,
    _vision_route,
)

_docs_enabled = os.environ.get("LIMA_DOCS_ENABLED", "").strip().lower() in {"1", "true", "yes"}
app = FastAPI(
    title="LiMa", version="1.3",
    description="LiMa（力码）— 智能编程助手 API，OpenAI 兼容",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Sentry error tracking
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        _sentry_integrations = [FastApiIntegration()]
        try:
            from sentry_sdk.integrations.httpx import HttpxIntegration
            _sentry_integrations.append(HttpxIntegration())
        except ImportError:
            pass

        def _filter_sensitive(event, hint):
            """Strip API keys and tokens from Sentry events."""
            for key in ("Authorization", "X-Api-Key", "x-api-key", "Cookie"):
                try:
                    headers = event.get("request", {}).get("headers", {})
                    if key in headers:
                        headers[key] = "[REDACTED]"
                except (AttributeError, TypeError):
                    pass
            return event

        sentry_sdk.init(
            dsn=_sentry_dsn,
            release=os.environ.get("LIMA_VERSION", "lima@1.3"),
            environment=os.environ.get("LIMA_ENV", "production"),
            send_default_pii=False,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.1")),
            integrations=_sentry_integrations,
            before_send=_filter_sensitive,
        )
    except ImportError:
        _log.debug("server: optional module not available", exc_info=True)
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

from routes.chat_handler import handle_chat as _handle_chat
from routes.chat_handler import inject_deps as _inject_chat_handler_deps
from routes.chat_stream import inject_deps as _inject_chat_stream_deps
from routes.chat_support import log_sys_prompt as _log_sys_prompt
from routes.chat_support import thinking_route as _thinking_route
from routes.images import build_pollinations_url as _build_pollinations_url

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
)
from routes.anthropic_stream import (
    anthropic_stream_passthrough as _anthropic_stream_passthrough,
)
from routes.anthropic_stream import (
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
    warmup_router_model()
    uvicorn.run(app, host="0.0.0.0", port=8080)
