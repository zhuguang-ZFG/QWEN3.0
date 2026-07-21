"""Workspace resolution for path generation (profile → product → DEFAULT)."""

from __future__ import annotations

import logging
import math
from typing import Any

from device_gateway.safety import DEFAULT_WORKSPACE_MM

_log = logging.getLogger(__name__)


def workspace_axes_ok(workspace_mm: Any) -> bool:
    """True when x/y/z are finite and strictly positive."""
    if not isinstance(workspace_mm, dict):
        return False
    for axis in ("x", "y", "z"):
        val = workspace_mm.get(axis)
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return False
        if not math.isfinite(float(val)) or float(val) <= 0:
            return False
    return True


def is_complete_profile(profile: Any) -> bool:
    """Complete requires non-empty profile_id and a usable workspace."""
    if profile is None:
        return False
    profile_id = str(getattr(profile, "profile_id", "") or "").strip()
    if not profile_id or profile_id.startswith("conservative-"):
        return False
    return workspace_axes_ok(getattr(profile, "workspace_mm", None))


def _default_workspace() -> dict[str, float]:
    return {k: float(v) for k, v in DEFAULT_WORKSPACE_MM.items()}


def _as_workspace(raw: dict[str, Any]) -> dict[str, float] | None:
    """Normalize workspace; None if non-finite or <= 0. Fills missing axes from DEFAULT."""
    try:
        out = {
            "x": float(raw["x"]) if "x" in raw else float(DEFAULT_WORKSPACE_MM["x"]),
            "y": float(raw["y"]) if "y" in raw else float(DEFAULT_WORKSPACE_MM["y"]),
            "z": float(raw["z"]) if "z" in raw else float(DEFAULT_WORKSPACE_MM["z"]),
        }
    except (TypeError, ValueError, KeyError):
        return None
    return out if workspace_axes_ok(out) else None


def _from_profile_obj(profile: Any) -> dict[str, float] | None:
    pw = getattr(profile, "workspace_mm", None) if profile is not None else None
    if not isinstance(pw, dict) or not pw:
        return None
    ws = _as_workspace(pw)
    if ws is None:
        _log.warning("invalid profile workspace %r; ignoring", pw)
    return ws


def _from_device_id(device_id: str) -> dict[str, float]:
    from device_gateway.profiles import PRODUCT_WRITING_WORKSPACE_MM, resolve_profile

    resolved = resolve_profile(device_id=device_id)
    if resolved.complete:
        ws = _from_profile_obj(resolved.profile)
        if ws is not None:
            return ws
        _log.warning("complete profile invalid workspace device_id=%s", device_id)
    product = _as_workspace(PRODUCT_WRITING_WORKSPACE_MM)
    return product if product is not None else _default_workspace()


def resolve_workspace_mm(
    workspace_mm: dict[str, Any] | None = None,
    *,
    device_id: str | None = None,
    profile: Any = None,
) -> dict[str, float]:
    """Pick workspace: explicit → profile → complete device profile → product/DEFAULT."""
    if isinstance(workspace_mm, dict) and workspace_mm:
        if all(k in workspace_mm for k in ("x", "y", "z")):
            ws = _as_workspace(workspace_mm)
            if ws is not None:
                return ws
        _log.warning("invalid or partial explicit workspace %r; ignoring", workspace_mm)
    ws = _from_profile_obj(profile)
    if ws is not None:
        return ws
    if device_id:
        try:
            return _from_device_id(device_id)
        except Exception:
            _log.warning(
                "resolve_workspace_mm failed for device_id=%s; using DEFAULT",
                device_id,
                exc_info=True,
            )
    return _default_workspace()
