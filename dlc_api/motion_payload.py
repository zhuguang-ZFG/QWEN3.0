"""Build motion_task payloads for /dlc/tasks/dispatch (keeps routes.py slim)."""

from __future__ import annotations

from typing import Any

from dlc_api.schemas import TaskDispatchRequest
from dlc_core import handle_draw, handle_draw_from_image, handle_write
from device_gateway.image_url_validation import validate_image_url_async
from device_gateway.path_pipeline import render_svg_task
from device_gateway.safety import DEFAULT_FEED


def _motion_task(text: str, request_id: str, entrypoint: str) -> dict[str, Any]:
    return {"text": text, "request_id": request_id, "source": "dlc_api", "entrypoint": entrypoint}


def _run_path_voice_task(*, path: list[dict[str, Any]], entrypoint: str) -> dict[str, Any]:
    return {
        "capability": "run_path",
        "params": {"path": path, "feed": DEFAULT_FEED, "source_capability": entrypoint},
        "source": "dlc_api",
        "entrypoint": entrypoint,
    }


def _voice_motion_task(
    text: str,
    request_id: str,
    entrypoint: str,
    svg_path: str,
    *,
    device_id: str | None = None,
) -> dict[str, Any]:
    rendered = render_svg_task(svg_path, device_id=device_id)
    motion_task = _motion_task(text, request_id, entrypoint)
    motion_task["voice_task"] = _run_path_voice_task(path=rendered["path"], entrypoint=entrypoint)
    return motion_task


def _path_motion_task(
    text: str,
    request_id: str,
    entrypoint: str,
    path: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach precomputed path so dispatch skips NL re-parse (write_text)."""
    motion_task = _motion_task(text, request_id, entrypoint)
    motion_task["voice_task"] = _run_path_voice_task(path=path, entrypoint=entrypoint)
    return motion_task


async def _payload_write_text(body: TaskDispatchRequest) -> tuple[dict[str, Any], dict[str, Any] | None]:
    text = str(body.payload.get("text", "")).strip()
    if not text:
        return {"status": "failed", "error": "text is required"}, None
    result = await handle_write(text, device_id=body.device_id)
    if result.get("status") == "success" and result.get("path_data"):
        return result, _path_motion_task(f"写{text}", body.request_id, "write_text", list(result["path_data"]))
    if result.get("status") == "success":
        return {"status": "failed", "error": "write succeeded but produced no path_data"}, None
    return result, None


async def _payload_draw_generated(body: TaskDispatchRequest) -> tuple[dict[str, Any], dict[str, Any] | None]:
    prompt = str(body.payload.get("prompt", "")).strip()
    if not prompt:
        return {"status": "failed", "error": "prompt is required"}, None
    result = await handle_draw(prompt, device_id=body.device_id, allow_dashscope=False)
    if result.get("status") == "success" and result.get("svg_path"):
        return result, _voice_motion_task(
            f"画{prompt}", body.request_id, "draw_generated", result["svg_path"], device_id=body.device_id
        )
    if result.get("status") == "success":
        return {"status": "failed", "error": "draw succeeded but produced no svg_path"}, None
    return result, None


async def _payload_draw_from_image(body: TaskDispatchRequest) -> tuple[dict[str, Any], dict[str, Any] | None]:
    image_url, err = await validate_image_url_async(str(body.payload.get("image_url", "")))
    if err or image_url is None:
        return {"status": "failed", "error": err or "image_url is required"}, None
    result = await handle_draw_from_image(image_url, device_id=body.device_id)
    if result.get("status") == "success" and result.get("svg_path"):
        return result, _voice_motion_task(
            "描图", body.request_id, "draw_from_image", result["svg_path"], device_id=body.device_id
        )
    if result.get("status") == "success":
        return {"status": "failed", "error": "draw succeeded but produced no svg_path"}, None
    return result, None


async def build_dispatch_payload(
    body: TaskDispatchRequest,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Returns (dlc_core_result, motion_task). motion_task is None if unsupported."""
    if body.type == "write_text":
        return await _payload_write_text(body)
    if body.type == "draw_generated":
        return await _payload_draw_generated(body)
    if body.type == "draw_from_image":
        return await _payload_draw_from_image(body)
    return {"status": "failed", "error": "unsupported type"}, None
