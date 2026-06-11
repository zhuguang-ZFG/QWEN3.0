"""Device mode configuration for smart device workloads.

When LIMA_DEVICE_MODE=1, the chat pipeline runs in device-optimized mode:
- Skip web_search, code_context, skills injection (编码助手特性)
- Use device_llm_router thin wrapper instead of full routing_engine
- Optimize for drawing/writing machine scenarios
"""
import os


def is_device_mode() -> bool:
    """Check if device mode is enabled via environment variable."""
    return os.environ.get("LIMA_DEVICE_MODE", "").strip() == "1"


def should_skip_context_pipeline() -> bool:
    """Skip context_pipeline heavy operations in device mode."""
    return is_device_mode()
