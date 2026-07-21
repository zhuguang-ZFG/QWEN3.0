"""Async run-parameter builders for device task creation."""

from __future__ import annotations

import asyncio
import math
from typing import Any

from .device_draw_handler import handle_device_draw
from .image_url_validation import validate_image_url_async
from .model_routing import CONTROL_CAPABILITIES, looks_like_svg_path
from .path_pipeline import PathNormalizationError, render_svg_task, render_text_task
from .path_validator import MAX_FEED, MIN_FEED
from .safety import DEFAULT_FEED, safe_point
from .task_handwriting_params import build_handwriting_params

__all__ = [
    "build_draw_generated_params",
    "build_handwriting_params",
    "build_run_params_async",
]


def _clamp_feed(raw: Any, default: int = DEFAULT_FEED) -> int:
    """Clamp user-supplied feed to the safe range [MIN_FEED, MAX_FEED] mm/min."""
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return default
    # GW-R3-10: NaN/Inf survive min()/max() (IEEE 754 comparisons are all False),
    # so a non-finite feed would silently clamp to MAX_FEED. Reject to default,
    # matching the already-guarded sibling in task_handwriting_params._clamp_feed.
    if not math.isfinite(val):
        return default
    return int(max(MIN_FEED, min(MAX_FEED, val)))


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


def _gallery_image_id_from_params(params: dict[str, Any]) -> str:
    raw = params.get("galleryImageId") or params.get("gallery_image_id")
    return str(raw).strip() if raw else ""


def _account_id_from_params(params: dict[str, Any]) -> str:
    # Server-injected only; never trust client accountId/account_id (IDOR).
    raw = params.get("_account_id")
    return str(raw).strip() if raw else ""


_GALLERY_DRAW_MIME_TYPES = frozenset({"image/jpeg", "image/png"})


async def _resolve_gallery_draw_image(
    params: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """Return (image_url, gallery_image_id, error_msg)."""
    gallery_image_id = _gallery_image_id_from_params(params)
    if not gallery_image_id:
        return None, None, None

    account_id = _account_id_from_params(params)
    if not account_id:
        return None, None, "gallery_image_id requires authenticated account context"

    from device_gateway import gallery_store
    from device_gateway.gallery_service import internal_gallery_file_url

    # GW-WD: gallery_store.get_image is synchronous SQLite — keep it off the loop.
    image = await asyncio.to_thread(gallery_store.get_image, gallery_image_id, account_id)
    if image is None:
        return None, None, "gallery image not found"

    mime = str(image.get("mimeType") or image.get("mime_type") or "").lower()
    if mime not in _GALLERY_DRAW_MIME_TYPES:
        return None, None, f"unsupported image type for draw: {mime or 'unknown'}"

    image_url = internal_gallery_file_url(account_id, gallery_image_id)
    if not image_url:
        return None, None, "gallery image URL could not be resolved"

    return image_url, gallery_image_id, None


def _svg_path_draw_params(
    prompt: str,
    user_feed: float,
    *,
    device_id: str | None = None,
) -> dict[str, Any]:
    rendered = render_svg_task(prompt, device_id=device_id)
    return {
        "feed": user_feed,
        "path": rendered["path"],
        "source_capability": "draw_generated",
        "prompt": prompt,
        "preview_svg": rendered.get("preview_svg", ""),
    }


async def _resolve_draw_image_url(params: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Return (image_url, gallery_image_id, error)."""
    gallery_image_url, gallery_image_id, gallery_error = await _resolve_gallery_draw_image(params)
    if gallery_error:
        return None, None, gallery_error
    if gallery_image_url:
        return gallery_image_url, gallery_image_id, None

    provided_image_url = params.get("imageUrl") or params.get("image_url")
    if not provided_image_url:
        return None, None, None
    validated_url, url_error = await validate_image_url_async(str(provided_image_url))
    if url_error or validated_url is None:
        return None, None, url_error or "image_url is invalid"
    return validated_url, None, None


def _finalize_draw_run_params(
    *,
    user_feed: float,
    draw_prompt: str,
    result: dict[str, Any],
    gallery_image_id: str | None,
    provided_image_url: str | None,
    device_id: str | None = None,
) -> dict[str, Any]:
    rendered = render_svg_task(str(result["svg_path"]), device_id=device_id)
    run_params: dict[str, Any] = {
        "feed": user_feed,
        "path": rendered["path"],
        "source_capability": "draw_generated",
        "prompt": draw_prompt[:120],
        "preview_svg": rendered.get("preview_svg", ""),
    }
    if gallery_image_id:
        run_params["gallery_image_id"] = gallery_image_id[:64]
    else:
        returned_image_url = result.get("image_url") or provided_image_url
        if isinstance(returned_image_url, str) and returned_image_url:
            run_params["image_url"] = returned_image_url[:512]
    model = result.get("model")
    if isinstance(model, str) and model:
        run_params["draw_model"] = model[:80]
    return run_params


async def build_draw_generated_params(
    prompt: str, device_id: str, params: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    user_feed = _clamp_feed(params.get("feed"))
    if _looks_like_svg_path(prompt):
        try:
            return _svg_path_draw_params(prompt, user_feed, device_id=device_id), None
        except PathNormalizationError as exc:
            return {}, f"path normalization failed: {exc}"

    provided_image_url, gallery_image_id, image_error = await _resolve_draw_image_url(params)
    if image_error:
        return {}, image_error

    draw_prompt = prompt.strip()
    if not draw_prompt and gallery_image_id:
        draw_prompt = f"gallery:{gallery_image_id[:32]}"

    result = await handle_device_draw(
        draw_prompt,
        device_id=device_id,
        user_preferences=_draw_user_preferences(params),
        image_url=str(provided_image_url) if provided_image_url else None,
    )
    if result.get("status") != "success" or not result.get("svg_path"):
        return {}, str(result.get("error") or "draw generation failed")

    try:
        run_params = _finalize_draw_run_params(
            user_feed=user_feed,
            draw_prompt=draw_prompt,
            result=result,
            gallery_image_id=gallery_image_id,
            provided_image_url=provided_image_url,
            device_id=device_id,
        )
    except PathNormalizationError as exc:
        return {}, f"path normalization failed: {exc}"
    return run_params, None


async def build_run_params_async(
    capability: str, params: dict[str, Any], device_id: str
) -> tuple[dict[str, Any], str | None]:
    if capability == "write_text":
        try:
            rendered = render_text_task(str(params.get("text", "")), device_id=device_id)
        except PathNormalizationError as exc:
            return {}, f"path normalization failed: {exc}"
        return {
            "feed": _clamp_feed(params.get("feed")),
            "path": rendered["path"],
            "source_capability": "write_text",
            "text": str(params.get("text", ""))[:80],
            "preview_svg": rendered.get("preview_svg", ""),
        }, None
    if capability == "draw_generated":
        prompt = str(params.get("prompt", ""))[:120]
        return await build_draw_generated_params(prompt, device_id, params)
    if capability == "run_path":
        # Pre-parsed path from dlc_api; use the already-rendered path from params.
        return {
            "feed": _clamp_feed(params.get("feed")),
            "path": params.get("path", [safe_point(0, 0, 0)]),
            "source_capability": params.get("source_capability", "run_path"),
        }, None
    if capability == "handwriting":
        return await build_handwriting_params(params, device_id)
    if capability in CONTROL_CAPABILITIES:
        return {"source_capability": capability}, None
    if capability in ("move_abs", "move_rel"):
        # GW-R3-12: point-to-point motion. Pass scalar axis params through
        # untouched (no path generation); validate_capability_params enforces
        # bounds/jog limits downstream. Copy only the axis + feed scalars.
        move_keys = ("x", "y", "z") if capability == "move_abs" else ("dx", "dy", "dz")
        passthrough: dict[str, Any] = {"source_capability": capability}
        for key in (*move_keys, "feed"):
            if key in params:
                passthrough[key] = params[key]
        return passthrough, None
    return {"feed": DEFAULT_FEED, "path": [safe_point(0, 0, 0)], "source_capability": capability}, None
