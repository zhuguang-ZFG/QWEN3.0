"""Async run-parameter builders for device task creation."""

from __future__ import annotations

from typing import Any

from .device_draw_handler import handle_device_draw
from .model_routing import CONTROL_CAPABILITIES, looks_like_svg_path
from .path_pipeline import render_svg_task, render_text_task
from .safety import DEFAULT_FEED, safe_point


def _looks_like_svg_path(text: str) -> bool:
    return looks_like_svg_path(text)


def _draw_user_preferences(params: dict[str, Any]) -> dict[str, Any]:
    prefs: dict[str, Any] = {}
    model = params.get("model")
    size = params.get("size")
    if isinstance(model, str) and model.strip():
        prefs["model"] = model.strip()
    if isinstance(size, str) and size.strip():
        prefs["size"] = size.strip()
    return prefs


async def build_draw_generated_params(
    prompt: str, device_id: str, params: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    if _looks_like_svg_path(prompt):
        rendered = render_svg_task(prompt)
        return {
            "feed": DEFAULT_FEED,
            "path": rendered["path"],
            "source_capability": "draw_generated",
            "prompt": prompt,
            "preview_svg": rendered.get("preview_svg", ""),
        }, None

    result = await handle_device_draw(prompt, device_id=device_id, user_preferences=_draw_user_preferences(params))
    if result.get("status") != "success" or not result.get("svg_path"):
        error = str(result.get("error") or "draw generation failed")
        return {}, error

    rendered = render_svg_task(str(result["svg_path"]))
    run_params: dict[str, Any] = {
        "feed": DEFAULT_FEED,
        "path": rendered["path"],
        "source_capability": "draw_generated",
        "prompt": prompt,
        "preview_svg": rendered.get("preview_svg", ""),
    }
    image_url = result.get("image_url")
    if isinstance(image_url, str) and image_url:
        run_params["image_url"] = image_url[:512]
    model = result.get("model")
    if isinstance(model, str) and model:
        run_params["draw_model"] = model[:80]
    return run_params, None


async def build_run_params_async(
    capability: str, params: dict[str, Any], device_id: str
) -> tuple[dict[str, Any], str | None]:
    if capability == "write_text":
        rendered = render_text_task(str(params.get("text", "")))
        return {
            "feed": DEFAULT_FEED,
            "path": rendered["path"],
            "source_capability": "write_text",
            "text": str(params.get("text", ""))[:80],
            "preview_svg": rendered.get("preview_svg", ""),
        }, None
    if capability == "draw_generated":
        prompt = str(params.get("prompt", ""))[:120]
        return await build_draw_generated_params(prompt, device_id, params)
    if capability in CONTROL_CAPABILITIES:
        return {"source_capability": capability}, None
    return {"feed": DEFAULT_FEED, "path": [safe_point(0, 0, 0)], "source_capability": capability}, None
