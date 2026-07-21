"""Honest dispatch status helpers for device delivery (M1 online push)."""

from __future__ import annotations

QUEUED_NO_DELIVERY_STATUS = "queued_no_delivery"

QUEUED_NO_DELIVERY_USER_MESSAGE = (
    "路径已生成并入队，但设备当前未连接云端下发通道（/device/v1/ws），不会运动。"
    "请让设备完成 hello 连接，或使用设备端语音/固件本地 MCP（self.plotter）。"
)

QUEUED_NO_DELIVERY_MCP_MESSAGE = (
    "路径已生成但设备未连接 DLC 下发通道。请设备连接 wss://…/device/v1/ws 并 hello，或使用设备端语音/固件本地 MCP。"
)


def apply_queued_no_delivery_fields(payload: dict[str, object], dispatch_status: str) -> None:
    """Augment API payloads when tasks are queued without a live delivery path."""
    if dispatch_status != QUEUED_NO_DELIVERY_STATUS:
        return
    payload["deliveryAvailable"] = False
    payload["message"] = QUEUED_NO_DELIVERY_USER_MESSAGE
