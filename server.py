"""server.py — LiMa（力码）OpenAI 兼容接口层
让 Cursor、Claude Code、VS Code Copilot 等 AI IDE 直接接入。
支持流式/非流式 ChatCompletion，兼容 OpenAI API 格式。
"""

import sys, os, logging as _logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Bootstrap a minimal logger before any application logging is configured.
_boot_log = _logging.getLogger("lima.bootstrap")

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    _boot_log.warning("python-dotenv not installed; .env file will not be loaded")

from fastapi import FastAPI
import uvicorn

from vision_handler import (
    _vision_route,
    _stream_vision_response,
)
from http_body_limit import BodySizeLimitMiddleware
from lima_constants import MODEL_VERSION
from server_bootstrap import (
    MAX_BODY_SIZE,
    MODEL_CREATED,
    MODEL_ID,
    create_runtime_state,
    last_resort_call as _last_resort_call,
)
from server_lifespan import lifespan

app = FastAPI(
    title="LiMa",
    version=MODEL_VERSION,
    description="LiMa（力码）— 智能编程助手 API，OpenAI 兼容",
    lifespan=lifespan,
)

_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            send_default_pii=False,
            enable_logs=True,
            traces_sample_rate=0.1,
            integrations=[FastApiIntegration()],
        )
    except ImportError:
        _boot_log.warning("SENTRY_DSN is set but sentry_sdk is not installed; error tracking disabled")

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

from routes.images import build_pollinations_url as _build_pollinations_url

from routes.chat_handler import handle_chat as _handle_chat, inject_deps as _inject_chat_handler_deps
from routes.chat_stream import inject_deps as _inject_chat_stream_deps

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
        handle_chat=lambda *args, **kwargs: _handle_chat(*args, **kwargs),
    ),
)
chat_completions = _registered.chat_completions
list_models = _registered.list_models
health = _registered.health
live_key = _registered.live_key
router_status = _registered.router_status

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
