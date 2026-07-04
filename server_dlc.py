"""DLC production entry point — only registers DLC routes.

Run:
    python -m uvicorn server_dlc:app --host 127.0.0.1 --port 8080

This is the slimmed-down production server for the XiaoZhi + DLC architecture.
It does NOT register any LiMa chat/admin/voice/provider routes.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from dlc_api.routes import router as dlc_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="DLC Drawing Service", version="0.3.0-p3")
app.include_router(dlc_router)


@app.on_event("startup")
async def _log_startup() -> None:
    logger.info("DLC server started — /health, /dlc/tasks/*, /dlc/devices/*")
