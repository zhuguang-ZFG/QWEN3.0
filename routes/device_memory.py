"""Device memory management routes for parent/admin."""
from fastapi import APIRouter

router = APIRouter(prefix="/device/memory", tags=["device_memory"])

# TODO: Add routes for:
# - GET /device/{device_id}/memories - list memories
# - DELETE /device/{device_id}/memories/{memory_id} - delete memory
# - POST /device/{device_id}/memories/{memory_id}/disable - disable memory
# - GET /device/{device_id}/memories/export - export memories
# - POST /device/{device_id}/memories/reset - reset all memories
