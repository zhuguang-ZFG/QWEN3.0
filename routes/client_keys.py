"""Admin API routes for client API key management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

import client_keys
from client_keys.models import ClientKey
from client_keys.storage import _mask_key
from client_keys.validation import (
    KeyCreateRequest,
    KeyListResponse,
    KeyMutationResponse,
    KeyRegenerateRequest,
    KeyResponse,
    KeyUpdateRequest,
)
from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()
_log = logging.getLogger(__name__)


def _key_to_response(key: ClientKey) -> KeyResponse:
    usage = client_keys.get_usage_summary(key.key_value)
    return KeyResponse(
        key_id=key.key_id,
        key_masked=_mask_key(key.key_value),
        label=key.label,
        enabled=key.enabled,
        created_at=key.created_at,
        last_used_at=usage.get("last_used_at") or key.created_at,
        request_count=0,
        quota_daily=key.quota_daily,
        quota_monthly=key.quota_monthly,
        rate_limit_rpm=key.rate_limit_rpm,
        allowed_urls=key.allowed_urls,
        usage_daily=usage.get("daily_count", 0),
        usage_monthly=usage.get("monthly_count", 0),
    )


@router.get("/admin/api/client-keys", dependencies=[Depends(verify_admin)])
async def list_client_keys() -> KeyListResponse:
    keys = client_keys.storage().list_all()
    return KeyListResponse(keys=[_key_to_response(k) for k in keys], total=len(keys))


@router.post(
    "/admin/api/client-keys",
    dependencies=[Depends(verify_admin), Depends(verify_csrf)],
    response_model=KeyMutationResponse,
    response_model_exclude_none=True,
)
async def create_client_key(body: KeyCreateRequest) -> KeyMutationResponse:
    key = client_keys.storage().create(
        label=body.label,
        quota_daily=body.quota_daily,
        quota_monthly=body.quota_monthly,
        rate_limit_rpm=body.rate_limit_rpm,
        allowed_urls=body.allowed_urls,
    )
    _log.info("admin: created client key %s label=%s", key.key_id, key.label)
    key_value = key.key_value if body.reveal else None
    if body.reveal:
        _log.warning("admin: revealing raw key_value for %s", key.key_id)
    return KeyMutationResponse(
        key_id=key.key_id,
        key_masked=_mask_key(key.key_value),
        key_value=key_value,
    )


@router.put(
    "/admin/api/client-keys/{key_id}",
    dependencies=[Depends(verify_admin), Depends(verify_csrf)],
    response_model=KeyMutationResponse,
    response_model_exclude_none=True,
)
async def update_client_key(key_id: str, body: KeyUpdateRequest) -> KeyMutationResponse:
    updates = body.model_dump(exclude_unset=True)
    updates.pop("allowed_urls", None)
    if body.allowed_urls is not None:
        updates["allowed_urls"] = body.allowed_urls
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = client_keys.storage().update(key_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Key '{key_id}' not found")
    _log.info("admin: updated client key %s", key_id)
    return KeyMutationResponse(key_id=key_id)


@router.delete(
    "/admin/api/client-keys/{key_id}",
    dependencies=[Depends(verify_admin), Depends(verify_csrf)],
    response_model=KeyMutationResponse,
    response_model_exclude_none=True,
)
async def delete_client_key(key_id: str) -> KeyMutationResponse:
    ok = client_keys.storage().delete(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Key '{key_id}' not found")
    _log.info("admin: deleted client key %s", key_id)
    return KeyMutationResponse(key_id=key_id, deleted=key_id)


@router.post(
    "/admin/api/client-keys/{key_id}/regenerate",
    dependencies=[Depends(verify_admin), Depends(verify_csrf)],
    response_model=KeyMutationResponse,
    response_model_exclude_none=True,
)
async def regenerate_client_key(key_id: str, body: KeyRegenerateRequest) -> KeyMutationResponse:
    old_key = client_keys.storage().get_by_key_id(key_id)
    if old_key is None:
        raise HTTPException(status_code=404, detail=f"Key '{key_id}' not found")
    client_keys.quota().clear_token(old_key.key_value)
    new_key = client_keys.storage().regenerate(key_id)
    if new_key is None:
        raise HTTPException(status_code=404, detail=f"Key '{key_id}' not found")
    _log.info("admin: regenerated client key %s", key_id)
    key_value = new_key.key_value if body.reveal else None
    if body.reveal:
        _log.warning("admin: revealing raw key_value for %s", key_id)
    return KeyMutationResponse(
        key_id=key_id,
        key_masked=_mask_key(new_key.key_value),
        key_value=key_value,
    )
