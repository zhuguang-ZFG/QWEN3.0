"""Pydantic request/response models for the dlc_api P1 routes.

Extracted from ``dlc_api/routes.py`` to keep that module under the 300-line
size gate. The route handlers import these back by name, so the public
contract is unchanged.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskPreviewRequest(BaseModel):
    """Request to generate a path preview without dispatching."""

    type: str = Field(..., pattern=r"^(write_text|draw_generated|draw_from_image)$")
    device_id: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class TaskDispatchRequest(BaseModel):
    """Request to generate a path and dispatch it to the device."""

    type: str = Field(..., pattern=r"^(write_text|draw_generated|draw_from_image)$")
    device_id: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(default="")


class TaskPreviewResponse(BaseModel):
    """Result of a preview request."""

    status: str
    path_data: list[dict[str, Any]] | None = None
    svg_path: str | None = None
    preview_svg: str | None = None
    width: int | None = None
    height: int | None = None
    model: str | None = None
    error: str | None = None


class TaskDispatchResponse(BaseModel):
    """Result of a dispatch request."""

    status: str
    task_id: str | None = None
    queue_depth: int = 0
    error: str | None = None


class DeviceStatusResponse(BaseModel):
    """Canonical device status payload for DLC MCP callers."""

    device_id: str
    online: bool
    working: bool
    active_task_id: str | None = None
    firmware_version: str | None = None
    last_seen_at: str | None = None
    shadow: dict[str, Any] = Field(default_factory=dict)


class TaskValidateRequest(BaseModel):
    """Request to validate a motion path against safety rules."""

    # CORE-O4: pydantic v2 accepts NaN/Infinity floats by default; a NaN
    # workspace bound defeats every boundary comparison downstream. Reject
    # non-finite numbers at the parsing layer.
    model_config = ConfigDict(allow_inf_nan=False)

    path: list[dict[str, Any]] = Field(..., min_length=1)
    workspace: dict[str, float] | None = None


class TaskValidateResponse(BaseModel):
    """Result of a path validation request."""

    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
