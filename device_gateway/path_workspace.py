"""Workspace resolution for path generation (profile → product → DEFAULT)."""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.safety import DEFAULT_WORKSPACE_MM

_log = logging.getLogger(__name__)


def _as_workspace(raw: dict[str, Any]) -> dict[str, float]:
    return {
        "x": float(raw.get("x", DEFAULT_WORKSPACE_MM["x"])),
        "y": float(raw.get("y", DEFAULT_WORKSPACE_MM["y"])),
        "z": float(raw.get("z", DEFAULT_WORKSPACE_MM["z"])),
    }


def resolve_workspace_mm(
    workspace_mm: dict[str, Any] | None = None,
    *,
    device_id: str | None = None,
    profile: Any = None,
) -> dict[str, float]:
    """Pick workspace for path generation: explicit → profile → device resolve → DEFAULT.

    Complete profiles (registry by device_id, KNOWN by device_id, or profile_id)
    win. Incomplete/unknown devices with a device_id use the product writing
    canvas (300×300×80), not the 60mm conservative routing defaults. Callers
    without device_id use DEFAULT_WORKSPACE_MM.
    """
    if isinstance(workspace_mm, dict) and workspace_mm:
        return _as_workspace(workspace_mm)
    if profile is not None:
        pw = getattr(profile, "workspace_mm", None)
        if isinstance(pw, dict) and pw:
            return resolve_workspace_mm(pw)
    if device_id:
        try:
            from device_gateway.profiles import PRODUCT_WRITING_WORKSPACE_MM, resolve_profile

            resolved = resolve_profile(device_id=device_id)
            if resolved.complete:
                pw = getattr(resolved.profile, "workspace_mm", None)
                if isinstance(pw, dict) and pw:
                    return resolve_workspace_mm(pw)
            return _as_workspace(PRODUCT_WRITING_WORKSPACE_MM)
        except Exception:
            _log.warning(
                "resolve_workspace_mm failed for device_id=%s; using DEFAULT",
                device_id,
                exc_info=True,
            )
    return _as_workspace(DEFAULT_WORKSPACE_MM)
