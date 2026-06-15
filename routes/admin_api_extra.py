"""Extra admin API endpoints for the redesigned admin panel (facade).

Sub-routers live in routes/admin_extra_*.py by domain.
"""

from __future__ import annotations

from fastapi import APIRouter

from routes.admin_extra_agent_tasks import router as agent_tasks_router
from routes.admin_extra_alerts import router as alerts_router
from routes.admin_extra_backend_edit import router as backend_edit_router
from routes.admin_extra_client_keys import router as client_keys_router
from routes.admin_extra_config import router as config_router
from routes.admin_extra_devices import router as devices_router
from routes.admin_extra_insights import router as insights_router
from routes.admin_extra_logs import broadcast_log, router as logs_router

router = APIRouter()
router.include_router(backend_edit_router)
router.include_router(insights_router)
router.include_router(agent_tasks_router)
router.include_router(config_router)
router.include_router(devices_router)
router.include_router(alerts_router)
router.include_router(client_keys_router)
router.include_router(logs_router)

__all__ = ["router", "broadcast_log"]
