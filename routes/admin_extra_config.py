"""Admin API: backend config export/import."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from routes.facade import BACKENDS, add_backend, has_backend
from routes.admin_auth import verify_admin, verify_csrf
from routes.admin_backends import _is_safe_backend_url
from routes.admin_state import stats_context

router = APIRouter()


@router.get("/api/config/export", dependencies=[Depends(verify_admin)])
async def config_export():
    """Export current backend configuration summary."""
    config: dict[str, Any] = {"version": "1.0", "exported_at": time.time()}
    config["backends"] = {
        name: {
            "url": cfg.get("url", ""),
            "model": cfg.get("model", ""),
            "fmt": cfg.get("fmt", "openai"),
            "tier": cfg.get("tier", ""),
            "caps": cfg.get("caps", []),
        }
        for name, cfg in BACKENDS.items()
    }
    _stats, _lock, backend_enabled = stats_context()
    config["backend_enabled"] = dict(backend_enabled)
    return config


@router.post("/api/config/import", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def config_import(req: Request):
    body = await req.json()
    if not body.get("version"):
        raise HTTPException(400, "Invalid config format: missing version")
    imported: list[str] = []
    new_backends = body.get("backends", {})
    for name, cfg in new_backends.items():
        if not has_backend(name):
            url = cfg.get("url", "")
            if url and not _is_safe_backend_url(url):
                raise HTTPException(400, f"unsafe backend URL for '{name}': must be a public HTTPS endpoint")
            add_backend(name, cfg)
            imported.append(name)
    return {"ok": True, "imported": imported}
