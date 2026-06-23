"""Admin API: backend mutation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from routes.facade import BACKENDS
from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()


@router.put("/api/backends/{name}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_edit_backend(name: str, req: Request):
    """Update an existing backend's URL, model, caps, or admission policy."""
    if name not in BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    body = await req.json()
    cfg = BACKENDS[name]
    for field in ("url", "model"):
        if field in body and body[field]:
            cfg[field] = body[field]
    if "caps" in body and isinstance(body["caps"], list):
        cfg["caps"] = body["caps"]
    if "admission" in body:
        cfg["admission"] = body["admission"]
    return {"ok": True, "name": name}
