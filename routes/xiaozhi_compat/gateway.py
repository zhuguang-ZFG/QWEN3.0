"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


from device_logic.gateway import build_gateway_task, dispatch_or_enqueue, gateway_capability

__all__ = ["build_gateway_task", "dispatch_or_enqueue", "gateway_capability"]
