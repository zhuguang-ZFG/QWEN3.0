"""DLC production entry point — DLC drawing + mini-program device-app routes.

Run:
    python -m uvicorn server_dlc:app --host 127.0.0.1 --port 8081

This is the slimmed-down production server for the XiaoZhi + DLC architecture.
It registers the DLC drawing routes plus the WeChat mini-program device-app
API (`/device/v1/app/*`). It does NOT register the retired LiMa
chat/admin/voice/provider or self-hosted device-gateway WS routes.
"""

from __future__ import annotations

import asyncio
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


async def _run_startup_recovery(logger: logging.Logger) -> None:
    """C1 Phase 3: background recovery of in-flight workflow tasks from ledger."""
    try:
        from device_gateway.store import task_store as _task_store
        from device_workflow.orchestrator import workflow as _workflow
        from device_workflow.startup_recovery import recover_inflight_tasks

        result = await asyncio.to_thread(recover_inflight_tasks, _task_store, _workflow, logger)
        logger.info("workflow startup recovery completed: %s", result)
    except Exception:
        logger.warning("workflow startup recovery failed", exc_info=True)


async def _cancel_background_task(task: asyncio.Task) -> None:
    """Cancel and drain a background task, ignoring CancelledError."""
    try:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    except Exception:
        logger.warning("取消后台任务失败", exc_info=True)


async def _close_backend_pools(logger: logging.Logger) -> None:
    """Gracefully close WebSocket sessions and Redis connection pools."""
    try:
        from device_gateway.sessions import registry as _reg

        for s in _reg.active_sessions():
            try:
                await s.websocket.close(code=1012, reason="server_restart")
            except Exception:
                logger.warning("关闭会话失败 device=%s", s.device_id, exc_info=True)
        from device_gateway.store import task_store as _ts

        if getattr(_ts, "backend_name", None) == "redis":
            _ts.close()
            logger.info("已关闭 Redis 连接池")
        from device_ledger.store import ledger_manager as _lm

        if getattr(_lm.store, "backend_name", None) == "redis":
            _lm.store.close()
            logger.info("已关闭 ledger Redis 连接池")
    except Exception:
        logger.warning("清理异常", exc_info=True)


# P1: disable interactive docs on the public entrypoint (SEC-05).
@asynccontextmanager
async def lifespan(app: FastAPI):
    from device_gateway.store import configure_task_store_from_env
    from device_ledger.store import configure_ledger_store_from_env

    try:
        configure_task_store_from_env()
    except Exception:
        logger.error("task store configuration failed", exc_info=True)
        raise
    # C1 Phase 1: 生产启用 ledger Redis 后端；配置失败即中止启动（不静默回退内存）。
    try:
        configure_ledger_store_from_env()
    except Exception:
        logger.error("ledger store configuration failed", exc_info=True)
        raise

    recovery_task = asyncio.create_task(_run_startup_recovery(logger))
    logger.info("DLC server started - /health, /dlc/*, /device/v1/app/*, /v1/voice")
    yield
    # --- 优雅关停：取消后台恢复任务 + 关闭 WebSocket 会话 + Redis 连接池 ---
    await _cancel_background_task(recovery_task)
    await _close_backend_pools(logger)


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
