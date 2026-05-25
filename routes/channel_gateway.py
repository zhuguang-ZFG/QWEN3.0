"""Channel Gateway FastAPI routes - sidecar API for WeChat binding and messaging."""

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/channel")

# -- Dependency injection (overridden in tests) -----------------------------

_store = None
_service = None


def _get_sidecar_token():
    return os.environ.get("LIMA_WECHAT_SIDECAR_TOKEN", "")


def _bridge_enabled():
    return os.environ.get("WECHAT_BRIDGE_ENABLED", "0") == "1"


def inject_deps(*, store, service):
    global _store, _service
    _store = store
    _service = service


def _reset_deps_for_test():
    global _store, _service
    _store = None
    _service = None


def _get_store():
    global _store
    if not os.environ.get("LIMA_CHANNEL_ID_SALT", "").strip():
        raise HTTPException(503, "LIMA_CHANNEL_ID_SALT not configured")
    if _store is None:
        from channel_gateway.store import ChannelStore

        db_path = os.environ.get("LIMA_CHANNEL_DB_PATH", "data/channel_gateway.db")
        _store = ChannelStore(db_path)
        _store._create_tables()
    return _store


def _get_service():
    global _service
    if _service is None:
        from channel_gateway.service import ChannelService

        _service = ChannelService(
            store=_get_store(),
            enabled=_bridge_enabled(),
            wire_integrations=True,
        )
    else:
        _service._enabled = _bridge_enabled()
    return _service


# -- Auth --------------------------------------------------------------------


async def _require_sidecar(authorization: str = Header(default="")):
    token = _get_sidecar_token()
    if not token:
        raise HTTPException(503, "LIMA_WECHAT_SIDECAR_TOKEN not configured")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(401, "Unauthorized")
    presented = authorization[len(prefix):].strip()
    if not hmac.compare_digest(presented, token):
        raise HTTPException(401, "Unauthorized")


# -- Request Models ----------------------------------------------------------


class BindStartRequest(BaseModel):
    channel: str = "wechat"
    lima_user_id: str = "owner"


class WechatMessageRequest(BaseModel):
    message_id: str
    sender_id: str
    conversation_id: str
    conversation_type: str = "private"
    text: str = ""
    timestamp: int = 0
    attachments: list = []


# -- Routes ------------------------------------------------------------------


@router.post("/v1/bind/start")
async def bind_start(req: BindStartRequest, _=Depends(_require_sidecar)):
    store = _get_store()
    code = store.create_binding_code(req.lima_user_id, ttl_seconds=300)
    expires_at = store._get_conn().execute(
        "SELECT expires_at FROM channel_binding_codes ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return {
        "binding_code": code,
        "expires_at": expires_at["expires_at"] if expires_at else 0,
        "instructions": f"Send /bind {code} to the WeChat robot.",
    }


@router.post("/v1/wechat/message")
async def wechat_message(req: WechatMessageRequest, _=Depends(_require_sidecar)):
    from channel_gateway.models import InboundMessage

    svc = _get_service()
    msg = InboundMessage(
        message_id=req.message_id,
        sender_id=req.sender_id,
        conversation_id=req.conversation_id,
        conversation_type=req.conversation_type,
        text=req.text,
        timestamp=req.timestamp,
        attachments=req.attachments or [],
    )
    result = svc.handle_message(msg)
    body = {"ok": result.ok}
    if result.reply is not None:
        body["reply"] = result.reply
    if result.error is not None:
        body["error"] = result.error
    return body


@router.get("/v1/wechat/health")
async def wechat_health(_=Depends(_require_sidecar)):
    store = _get_store()
    return {
        "enabled": _bridge_enabled(),
        "bound_users": store.get_binding_count(),
        "recent_messages": store.get_recent_message_count(limit=100),
    }
