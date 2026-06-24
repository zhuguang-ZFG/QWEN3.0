#!/usr/bin/env python3
"""Shared helpers used by the openapi_examples package."""

from __future__ import annotations

from typing import Any


__all__ = ["uuid", "parameter_with_example", "synthetic_query_param"]


def uuid(prefix: str) -> str:
    return f"{prefix}-00000000-0000-0000-0000-000000000001"


def synthetic_query_param(path: str) -> dict[str, Any]:
    """Create a plausible optional query parameter when an endpoint has none."""
    if "/auth/captcha" in path:
        return {
            "name": "width",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "default": 120, "title": "Width"},
        }
    return {
        "name": "locale",
        "in": "query",
        "required": False,
        "schema": {"type": "string", "default": "zh-CN", "title": "Locale"},
    }


def parameter_with_example(param: dict[str, Any]) -> dict[str, Any]:
    """Attach a sensible example to a parameter for request examples."""
    param = dict(param)
    name = param.get("name", "")
    schema = param.get("schema", {})
    typ = schema.get("type") if isinstance(schema, dict) else None

    if name == "authorization":
        example = "Bearer lima_api_token"
    elif name == "device_id":
        example = uuid("dev")
    elif name == "asset_id":
        example = uuid("ast")
    elif name == "session_id":
        example = uuid("sess")
    elif name == "task_id":
        example = uuid("tsk")
    elif name == "template_id":
        example = uuid("tpl")
    elif name == "voiceprint_id":
        example = uuid("vpr")
    elif name == "sub_id":
        example = uuid("sub")
    elif name == "transfer_id":
        example = uuid("trf")
    elif name == "share_token":
        example = uuid("shr")
    elif name == "audio_id":
        example = uuid("aud")
    elif typ == "integer":
        example = schema.get("default", 1)
    elif typ == "boolean":
        example = True
    else:
        example = schema.get("default") if schema.get("default") not in (None, "") else f"example_{name}"

    param["example"] = example
    return param
