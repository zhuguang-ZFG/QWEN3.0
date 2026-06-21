"""Shared device-app business logic (native + compat routes)."""

from device_logic.access import (
    device_access,
    expire_pending_transfers,
    is_owner,
    parse_supply_updates,
    require_device_access,
)
from device_logic.activation import (
    ACTIVATION_TTL_SECONDS,
    check_activation_code,
    new_activation_code,
    reset_activation_store_for_tests,
)
from device_logic.auth import account_payload, authorize, jwt, make_token
from device_logic.constants import (
    ALLOWED_MEMBER_ROLES,
    ALLOWED_SOURCES,
    ALLOWED_TASK_STATUSES,
    ALLOWED_TASKS,
)
from device_logic.crud import (
    bind_device,
    get_device_row,
    list_device_rows,
    manual_add_device,
    unbind_device,
    update_device_row,
)
from device_logic.db import connect, db_path
from device_logic.errors import DeviceLogicError
from device_logic.http import err, json_params, loads_json, new_id, now, read_body, str_field
from device_logic.payloads import device_payload, member_payload, task_payload
from device_logic.updates import ALLOWED_DEVICE_COLUMNS, parse_device_updates, sql_set_clause

__all__ = [
    "ACTIVATION_TTL_SECONDS",
    "ALLOWED_DEVICE_COLUMNS",
    "ALLOWED_MEMBER_ROLES",
    "ALLOWED_SOURCES",
    "ALLOWED_TASK_STATUSES",
    "ALLOWED_TASKS",
    "DeviceLogicError",
    "account_payload",
    "authorize",
    "bind_device",
    "check_activation_code",
    "connect",
    "db_path",
    "device_access",
    "device_payload",
    "err",
    "expire_pending_transfers",
    "get_device_row",
    "is_owner",
    "json_params",
    "jwt",
    "list_device_rows",
    "loads_json",
    "make_token",
    "manual_add_device",
    "member_payload",
    "new_activation_code",
    "new_id",
    "now",
    "parse_device_updates",
    "parse_supply_updates",
    "read_body",
    "require_device_access",
    "reset_activation_store_for_tests",
    "sql_set_clause",
    "str_field",
    "task_payload",
    "unbind_device",
    "update_device_row",
]
