"""DLC production entry point — DLC drawing + mini-program device-app routes.

Run:
    python -m uvicorn server_dlc:app --host 127.0.0.1 --port 8081

This is the slimmed-down production server for the XiaoZhi + DLC architecture.
It registers the DLC drawing routes plus the WeChat mini-program device-app
API (`/device/v1/app/*`). It does NOT register the retired LiMa
chat/admin/voice/provider or self-hosted device-gateway WS routes.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI

from dlc_api.device_app_router import register_device_app_routes
from dlc_api.middleware import add_body_size_limit, add_request_id_middleware
from dlc_api.routes import router as dlc_router
from routes import images as images_router
from routes.device_app_voice_ws import legacy_router

if os.environ.get("LIMA_STRUCTURED_LOGGING") == "1":
    from observability.structured_logging import setup_structured_logging

    setup_structured_logging(service="lima-dlc", version="0.4.0-p3")
else:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# P1: disable interactive docs on the public entrypoint (SEC-05).
@asynccontextmanager
async def lifespan(app: FastAPI):
    from device_gateway.store import configure_task_store_from_env

    try:
        configure_task_store_from_env()
    except Exception:
        logger.error("task store configuration failed", exc_info=True)
        raise
    logger.info("DLC server started - /health, /dlc/*, /device/v1/app/*, /v1/voice")
    yield
    # --- 优雅关停：关闭 WebSocket 会话 + Redis 连接池 ---
    try:
        from device_gateway.sessions import registry as _reg

        for s in _reg.active_sessions():
            try:
                await s.websocket.close(code=1012, reason="server_restart")
            except Exception:
                logger.warning("关闭会话失败 device=%s", s.device_id, exc_info=True)
        from device_gateway.store import task_store as _ts

        if getattr(_ts, "backend_name", None) == "redis":
            _ts._redis.close()
            logger.info("已关闭 Redis 连接池")
    except Exception:
        logger.warning("清理异常", exc_info=True)


app = FastAPI(
    lifespan=lifespan,
    title="DLC Drawing Service",
    version="0.4.0-p3",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
# SEC: 应用层请求体上限兜底（不只靠 nginx client_max_body_size；直连 :8081 时仍生效）。
add_body_size_limit(app, max_bytes=32 * 1024 * 1024)
add_request_id_middleware(app)
app.include_router(dlc_router)
app.include_router(images_router.router)
register_device_app_routes(app)
app.include_router(legacy_router)
