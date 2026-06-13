"""Shared utilities barrel for XiaoZhi v1 compatibility API."""

from __future__ import annotations

from .access import (
    device_access,
    expire_pending_transfers,
    is_owner,
    parse_supply_updates,
    require_device_access,
)
from .auth import _JWT_IMPORT_ERROR, account_payload, authorize, jwt, jwt_secret, make_token
from .constants import (
    ALLOWED_MEMBER_ROLES,
    ALLOWED_SOURCES,
    ALLOWED_TASK_STATUSES,
    ALLOWED_TASKS,
)
from .db import _schema_lock, _schema_ready_paths, connect, db_path, ensure_schema
from .gateway import build_gateway_task, dispatch_or_enqueue, gateway_capability
from .http_helpers import (
    err,
    expires_at,
    json_params,
    loads_json,
    new_id,
    now,
    ok,
    query_int,
    read_body,
    str_field,
)
from .payloads import (
    device_payload,
    member_payload,
    self_check_payload,
    supply_payload,
    task_payload,
    transfer_payload,
    voiceprint_payload,
)

__all__ = [
    "ALLOWED_MEMBER_ROLES",
    "ALLOWED_SOURCES",
    "ALLOWED_TASKS",
    "ALLOWED_TASK_STATUSES",
    "_JWT_IMPORT_ERROR",
    "_schema_lock",
    "_schema_ready_paths",
    "account_payload",
    "authorize",
    "build_gateway_task",
    "connect",
    "db_path",
    "device_access",
    "device_payload",
    "dispatch_or_enqueue",
    "ensure_schema",
    "err",
    "expire_pending_transfers",
    "expires_at",
    "gateway_capability",
    "is_owner",
    "json_params",
    "jwt",
    "jwt_secret",
    "loads_json",
    "make_token",
    "member_payload",
    "new_id",
    "now",
    "ok",
    "parse_supply_updates",
    "query_int",
    "read_body",
    "require_device_access",
    "self_check_payload",
    "str_field",
    "supply_payload",
    "task_payload",
    "transfer_payload",
    "voiceprint_payload",
]
