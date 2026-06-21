"""Backward-compatible re-export — canonical implementation in device_logic.gateway."""

from device_logic.gateway import build_gateway_task, dispatch_or_enqueue, gateway_capability

__all__ = ["build_gateway_task", "dispatch_or_enqueue", "gateway_capability"]
