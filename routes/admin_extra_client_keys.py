"""Admin API: client API key management.

Client keys are persisted to SQLite (routes/client_keys_store.py) so they
survive server restarts. The in-memory dict is loaded at import time and kept
in sync with the store on mutations.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from routes.admin_auth import verify_admin, verify_csrf
from routes.client_keys_store import delete_key, get_key, load_keys, record_usage, save_key

router = APIRouter()

_CLIENT_KEYS: dict[str, dict[str, Any]] = load_keys()


@router.get("/api/client-keys", dependencies=[Depends(verify_admin)])
async def list_client_keys():
    return {"keys": list(_CLIENT_KEYS.values())}


@router.post("/api/client-keys", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def create_client_key(req: Request):
    body = await req.json()
    label = body.get("label", "").strip()
    if not label:
        raise HTTPException(400, "label required")
    key_id = uuid.uuid4().hex[:16]
    key_value = f"lima-{uuid.uuid4().hex}"
    masked = key_value[:8] + "..." + key_value[-4:]
    entry = {
        "key_id": key_id,
        "key_masked": masked,
        "label": label,
        "enabled": True,
        "quota_daily": int(body.get("quota_daily", 1000)),
        "quota_monthly": int(body.get("quota_monthly", 30000)),
        "usage_daily": 0,
        "usage_monthly": 0,
        "rate_limit_rpm": int(body.get("rate_limit_rpm", 20)),
        "allowed_urls": body.get("allowed_urls", ["*"]),
        "last_used_at": 0,
        "created_at": time.time(),
    }
    _CLIENT_KEYS[key_id] = entry
    save_key(entry)
    return {"ok": True, "key_value": key_value, "key": entry}


@router.put("/api/client-keys/{key_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def update_client_key(key_id: str, req: Request):
    body = await req.json()
    entry = _CLIENT_KEYS.get(key_id)
    if not entry:
        raise HTTPException(404, "Key not found")
    for field in ("label", "enabled", "quota_daily", "quota_monthly", "rate_limit_rpm", "allowed_urls"):
        if field in body:
            entry[field] = body[field]
    save_key(entry)
    return {"ok": True, "key": entry}


@router.delete("/api/client-keys/{key_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def delete_client_key(key_id: str):
    if key_id not in _CLIENT_KEYS:
        raise HTTPException(404, "Key not found")
    del _CLIENT_KEYS[key_id]
    delete_key(key_id)
    return {"ok": True}


@router.post("/api/client-keys/{key_id}/regenerate", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def regenerate_client_key(key_id: str):
    entry = _CLIENT_KEYS.get(key_id)
    if not entry:
        raise HTTPException(404, "Key not found")
    key_value = f"lima-{uuid.uuid4().hex}"
    entry["key_masked"] = key_value[:8] + "..." + key_value[-4:]
    entry["regenerated_at"] = time.time()
    save_key(entry)
    return {"ok": True, "key_value": key_value}


@router.get("/api/client-keys/{key_id}/usage", dependencies=[Depends(verify_admin)])
async def client_key_usage(key_id: str):
    """Return current usage counters for a client API key."""
    entry = get_key(key_id)
    if entry is None:
        raise HTTPException(404, "Key not found")
    return {
        "key_id": key_id,
        "label": entry["label"],
        "usage_daily": entry["usage_daily"],
        "usage_monthly": entry["usage_monthly"],
        "quota_daily": entry["quota_daily"],
        "quota_monthly": entry["quota_monthly"],
        "last_used_at": entry["last_used_at"],
    }


@router.post("/api/client-keys/{key_id}/record-usage", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def client_key_record_usage(key_id: str):
    """Manually bump usage counters (for testing or backfill)."""
    if get_key(key_id) is None:
        raise HTTPException(404, "Key not found")
    record_usage(key_id)
    _CLIENT_KEYS[key_id] = get_key(key_id)
    return {"ok": True, "key": _CLIENT_KEYS[key_id]}
