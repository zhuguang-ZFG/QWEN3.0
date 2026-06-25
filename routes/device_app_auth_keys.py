"""Device app API key management routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.api_key import create_key, delete_key, list_keys
from device_logic.auth import authorize
from device_logic.auth_rate import allow_device_auth
from device_logic.http import err, read_body, str_field
from routes.request_tracking import client_ip

router = APIRouter(tags=["device-app-auth"])


def _authorized(authorization: str) -> dict[str, Any] | JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    return account


@router.post("/keys")
async def create_api_key(request: Request, authorization: str = Header(default="")):
    if not allow_device_auth("key_create", client_ip(request)):
        return err(429, "Too many key creation attempts", 429)
    account = _authorized(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    name = str_field(body, "name")
    if not name:
        return err(400, "name is required", 400)
    if len(name) > 64:
        return err(400, "name must be 64 characters or less", 400)
    return create_key(account["id"], name)


@router.get("/keys")
async def list_api_keys(authorization: str = Header(default="")):
    account = _authorized(authorization)
    if isinstance(account, JSONResponse):
        return account
    return {"keys": list_keys(account["id"])}


@router.delete("/keys/{key_id}")
async def delete_api_key(key_id: str, authorization: str = Header(default="")):
    account = _authorized(authorization)
    if isinstance(account, JSONResponse):
        return account
    if not delete_key(account["id"], key_id):
        return err(404, "Key not found", 404)
    return {"deleted": True}
