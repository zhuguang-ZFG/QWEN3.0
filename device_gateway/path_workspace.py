"""Workspace resolution for path generation (profile → product → DEFAULT)."""

from __future__ import annotations

from typing import Any

from device_gateway.safety import DEFAULT_WORKSPACE_MM


def resolve_workspace_mm(
    workspace_mm: dict[str, Any] | None = None,
    *,
    device_id: str | None = None,
    profile: Any = None,
) -> dict[str, float]:
    """Pick workspace for path generation: explicit → profile → device resolve → DEFAULT.

    Complete profiles win. Incomplete/unknown devices with a device_id use the
    product writing canvas (300×300×80), not the 60mm conservative routing
    defaults. Callers without device_id use DEFAULT_WORKSPACE_MM.
    """
    if isinstance(workspace_mm, dict) and workspace_mm:
        return {
            "x": float(workspace_mm.get("x", DEFAULT_WORKSPACE_MM["x"])),
            "y": float(workspace_mm.get("y", DEFAULT_WORKSPACE_MM["y"])),
            "z": float(workspace_mm.get("z", DEFAULT_WORKSPACE_MM["z"])),
        }
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
            return {
                "x": float(PRODUCT_WRITING_WORKSPACE_MM["x"]),
                "y": float(PRODUCT_WRITING_WORKSPACE_MM["y"]),
                "z": float(PRODUCT_WRITING_WORKSPACE_MM["z"]),
            }
        except Exception:
            pass
    return {
        "x": float(DEFAULT_WORKSPACE_MM["x"]),
        "y": float(DEFAULT_WORKSPACE_MM["y"]),
        "z": float(DEFAULT_WORKSPACE_MM["z"]),
    }
