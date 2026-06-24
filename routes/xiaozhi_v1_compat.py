"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


from __future__ import annotations

from fastapi import APIRouter

from routes.xiaozhi_compat.device_routes import router as device_router
from routes.xiaozhi_compat.member_routes import router as member_router
from routes.xiaozhi_compat.misc_routes import router as misc_router
from routes.xiaozhi_compat.task_routes import router as task_router
from routes.xiaozhi_compat.user_routes import router as user_router
from routes.xiaozhi_compat import shared

router = APIRouter(prefix="/api/v1", tags=["xiaozhi-v1-compat"])
router.include_router(user_router)
router.include_router(device_router)
router.include_router(task_router)
router.include_router(member_router)
router.include_router(misc_router)

# Backward-compat for tests (prefer routes.xiaozhi_compat.shared for new code)
_connect = shared.connect
_schema_ready_paths = shared._schema_ready_paths
jwt = shared.jwt
