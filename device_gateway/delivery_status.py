"""Honest dispatch status helpers for device delivery (M1 online push)."""

from __future__ import annotations

import logging

QUEUED_NO_DELIVERY_STATUS = "queued_no_delivery"
QUEUED_STATUS = "queued"
SENT_STATUS = "sent"

QUEUED_NO_DELIVERY_USER_MESSAGE = (
    "路径已生成并入队，但设备当前未连接云端下发通道（/device/v1/ws），不会运动。"
    "请让设备完成 hello 连接，或使用设备端语音/固件本地 MCP（self.plotter）。"
)

QUEUED_NO_DELIVERY_MCP_MESSAGE = (
    "路径已生成但设备未连接 DLC 下发通道。请设备连接 wss://…/device/v1/ws 并 hello，或使用设备端语音/固件本地 MCP。"
)

_log = logging.getLogger(__name__)


def apply_queued_no_delivery_fields(payload: dict[str, object], dispatch_status: str) -> None:
    """Augment API payloads when tasks are queued without a live delivery path."""
    if dispatch_status != QUEUED_NO_DELIVERY_STATUS:
        return
    payload["deliveryAvailable"] = False
    payload["message"] = QUEUED_NO_DELIVERY_USER_MESSAGE


async def try_deliver_and_classify(device_id: str) -> tuple[bool, str]:
    """Push pending queue if online; classify result honestly.

    Returns ``(sent, dispatch_status)``:
    - ``sent``: drain completed while a session was (or became) able to receive
    - ``queued_no_delivery``: no live session after push attempt (offline)
    - ``queued``: session present but drain incomplete (push error / partial)
    """
    try:
        from routes.device_gateway_dispatch import try_deliver_pending

        delivered = await try_deliver_pending(device_id)
    except Exception:
        _log.warning("try_deliver_pending failed device_id=%s", device_id, exc_info=True)
        delivered = False
    if delivered:
        return True, SENT_STATUS
    from device_gateway.sessions import registry

    if registry.get(device_id) is None:
        return False, QUEUED_NO_DELIVERY_STATUS
    return False, QUEUED_STATUS
