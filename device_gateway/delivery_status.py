"""Honest dispatch status helpers (self-hosted device WS retired)."""

from __future__ import annotations

QUEUED_NO_DELIVERY_STATUS = "queued_no_delivery"

QUEUED_NO_DELIVERY_USER_MESSAGE = (
    "路径已生成并入队，但当前无设备下发通道，设备不会运动。请使用设备端语音或固件本地 MCP（self.plotter）执行。"
)

QUEUED_NO_DELIVERY_MCP_MESSAGE = (
    "路径已生成但无法投递到设备（云端下发通道未连接）。请使用设备端语音或固件本地 MCP 执行。"
)


def apply_queued_no_delivery_fields(payload: dict[str, object], dispatch_status: str) -> None:
    """Augment API payloads when tasks are queued without a live delivery path."""
    if dispatch_status != QUEUED_NO_DELIVERY_STATUS:
        return
    payload["deliveryAvailable"] = False
    payload["message"] = QUEUED_NO_DELIVERY_USER_MESSAGE
