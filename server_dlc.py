"""DLC production entry point — DLC drawing + mini-program device-app routes.

Run:
    python -m uvicorn server_dlc:app --host 127.0.0.1 --port 8080

This is the slimmed-down production server for the XiaoZhi + DLC architecture.
It registers the DLC drawing routes plus the WeChat mini-program device-app
API (`/device/v1/app/*`). It does NOT register the retired LiMa
chat/admin/voice/provider or self-hosted device-gateway WS routes.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from dlc_api.device_app_router import register_device_app_routes
from dlc_api.routes import router as dlc_router
from routes import images as images_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="DLC Drawing Service", version="0.4.0-p3")
app.include_router(dlc_router)
app.include_router(images_router.router)
register_device_app_routes(app)


@app.on_event("startup")
async def _log_startup() -> None:
    logger.info("DLC server started — /health, /dlc/*, /device/v1/app/*")
