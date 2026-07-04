"""DLC core: pure algorithms and thin facades for device drawing/writing."""

from __future__ import annotations

from dlc_core.device_status import get_device_status
from dlc_core.dispatch import dispatch_task
from dlc_core.draw import handle_draw, handle_draw_from_image
from dlc_core.intent import parse_intent
from dlc_core.path_validator import validate_path
from dlc_core.presets import get_preset
from dlc_core.safety import DEFAULT_WORKSPACE_MM, MAX_PATH_POINTS
from dlc_core.write import handle_write

__all__ = [
    "DEFAULT_WORKSPACE_MM",
    "MAX_PATH_POINTS",
    "dispatch_task",
    "get_device_status",
    "get_preset",
    "handle_draw",
    "handle_draw_from_image",
    "handle_write",
    "parse_intent",
    "validate_path",
]
