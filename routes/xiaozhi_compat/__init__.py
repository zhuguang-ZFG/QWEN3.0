"""XiaoZhi v1 compatibility API submodules."""
from .shared import *

__all__ = [
    "ok", "err", "read_body", "connect", "authorize",
    "now", "new_id", "str_field", "query_int",
    "json_params", "loads_json", "device_access", "require_device_access",
    "device_payload", "task_payload", "member_payload", "account_payload",
]
