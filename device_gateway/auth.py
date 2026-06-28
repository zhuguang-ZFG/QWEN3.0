"""Device authentication helpers."""

from __future__ import annotations

import logging
import os
from hmac import compare_digest

from config.settings import DEVICE

_log = logging.getLogger(__name__)

# 固件直连兜底开关：固件 NVS 无 token（全代码无写入点），连 /ws 时 token 永远空。
# 开启后，token 为空但 device_id 是已注册设备（v2_device 表存在）时放行。
# 安全默认关闭：知道 device_id 即可空 token 连入 /device/v1/ws 是 CRITICAL 风险。
# U8 真机需运维在 .env 中显式设置 LIMA_WS_REGISTERED_DEVICE_FALLBACK=1。
_WS_REGISTERED_DEVICE_FALLBACK = os.environ.get("LIMA_WS_REGISTERED_DEVICE_FALLBACK", "0") == "1"


def configured_device_tokens() -> dict[str, str]:
    """Return device_id -> token entries from LIMA_DEVICE_TOKENS.

    Format: dev_a=token-a,dev_b=token-b. Newlines and semicolons are also
    accepted for ops convenience.
    """
    raw = DEVICE.tokens
    tokens: dict[str, str] = {}
    for chunk in raw.replace("\n", ",").replace(";", ",").split(","):
        item = chunk.strip()
        if not item or "=" not in item:
            continue
        device_id, token = item.split("=", 1)
        device_id = device_id.strip()
        token = token.strip()
        if device_id and token:
            tokens[device_id] = token
    return tokens


def _is_registered_device(device_id: str) -> bool:
    """Check if device_id (匹配 device_sn 或 id) 是已注册设备。

    device_id 来自固件 hello 消息；固件可能用 device_sn 或内部 id，故两者都查。
    """
    try:
        from device_logic.db import connect

        with connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM v2_device WHERE id=? OR device_sn=? LIMIT 1", (device_id, device_id)
            ).fetchone()
        return row is not None
    except Exception as exc:  # noqa: BLE001 - DB 故障不应阻断鉴权主路径
        _log.warning("registered device check failed for %r: %s", device_id, exc)
        return False


def validate_device_token(device_id: str, token: str) -> bool:
    expected = configured_device_tokens().get(device_id)
    if not expected and device_id == DEVICE.digital_human_default_device_id:
        expected = DEVICE.digital_human_default_token
    if expected and token:
        return compare_digest(expected, token)
    # 固件直连兜底：token 为空但设备已注册（v2_device 表存在）→ 放行。
    # 固件目前 NVS 无 token 写入点（XIAOZHI_INTEGRATION_GAP_CN.md TASK-6 铁证）。
    if (not token) and _WS_REGISTERED_DEVICE_FALLBACK and _is_registered_device(device_id):
        return True
    return False


def token_configured() -> bool:
    return bool(configured_device_tokens())
