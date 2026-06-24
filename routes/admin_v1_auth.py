"""Admin console v1 authentication API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from access_guard import extract_bearer_token
from device_logic.admin_auth import (
    ADMIN_ROLES,
    admin_payload,
    authenticate_admin,
    create_admin_user,
    decode_admin_token,
    make_admin_token,
)
from routes.admin_auth import verify_admin

router = APIRouter(prefix="/admin/v1")


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=1)


class CreateAdminRequest(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=8)
    nickname: str = ""
    role: str = "admin"


class TokenResponse(BaseModel):
    token: str
    user: dict


@router.post("/auth/login", response_model=TokenResponse)
async def admin_login(body: LoginRequest):
    user = authenticate_admin(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = make_admin_token(user)
    if not token:
        raise HTTPException(status_code=503, detail="JWT signing is not available")
    return {"token": token, "user": admin_payload(user)}


@router.get("/auth/me")
async def admin_me(authorization: str = Header(default="")):
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = decode_admin_token(token)
    if payload is None or payload.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }


@router.post("/auth/bootstrap", response_model=dict)
async def admin_bootstrap(
    body: CreateAdminRequest,
    _admin=Depends(verify_admin),
):
    """Create the first admin user. Protected by the existing static admin token."""
    try:
        user = create_admin_user(body.email, body.password, body.nickname, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "user": admin_payload(user)}
