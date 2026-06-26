"""Admin gray-observation metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from observability.metrics import get_metrics_snapshot
from routes.admin_auth import verify_admin

router = APIRouter()


@router.get("/api/metrics/gray", dependencies=[Depends(verify_admin)])
async def admin_gray_metrics() -> dict:
    """Return gray-observation metrics for semantic cache and Instructor intent."""
    return get_metrics_snapshot().get("gray_observation", {})
