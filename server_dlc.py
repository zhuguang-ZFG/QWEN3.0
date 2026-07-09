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

from fastapi import FastAPI

from dlc_api.device_app_router import register_device_app_routes
from dlc_api.middleware import add_body_size_limit
from dlc_api.routes import router as dlc_router
from routes import images as images_router
from routes.device_app_voice_ws import legacy_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# P1: disable interactive docs on the public entrypoint (SEC-05).
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DLC server started - /health, /dlc/*, /device/v1/app/*, /v1/voice")
    yield


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
app.include_router(dlc_router)
app.include_router(images_router.router)
register_device_app_routes(app)
app.include_router(legacy_router)
