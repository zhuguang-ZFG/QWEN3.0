"""Admin trace inspection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from observability.metrics import get_recent_traces
from routes.admin_auth import verify_admin

router = APIRouter()


@router.get("/api/traces/recent", dependencies=[Depends(verify_admin)])
async def admin_recent_traces(limit: int = Query(50, ge=1, le=1000)) -> dict:
    """Return the most recent request traces from the in-memory ring buffer."""
    return {"traces": get_recent_traces(limit)}
