"""Async run-parameter builders for device task creation."""

from __future__ import annotations

import logging
import time
from typing import Any

from integrations.autohanding.client import AutohandingRateLimitError
from observability import prometheus_metrics

from .device_draw_handler import handle_device_draw

_log = logging.getLogger(__name__)
from .model_routing import CONTROL_CAPABILITIES, looks_like_svg_path
from .path_pipeline import render_svg_task, render_text_task, text_to_svg_path
from .safety import DEFAULT_FEED, safe_point

# Feed rate bounds (mm/min), aligned with path_validator.MAX_FEED/MIN_FEED
_FEED_MIN = 1
_FEED_MAX = 2000


def _clamp_feed(raw: Any, default: int = DEFAULT_FEED) -> int:
    """Clamp user-supplied feed to the safe range [1, 2000] mm/min."""
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return default
    return max(_FEED_MIN, min(_FEED_MAX, val))


def _handwriting_options(params: dict[str, Any]) -> dict[str, Any]:
    from integrations.autohanding import constants

    return {
        "font_type": str(params.get("font_type", constants.DEFAULT_FONT_TYPE)),
        "paper_bg_type": str(params.get("paper_bg_type", constants.DEFAULT_PAPER_BG_TYPE)),
        "mistake_rate": int(params.get("mistake_rate", constants.DEFAULT_MISTAKE_RATE)),
        "messy_ratio": int(params.get("messy_ratio", constants.DEFAULT_MESSY_RATIO)),
        "char_random": int(params.get("char_random", constants.DEFAULT_CHAR_RANDOM)),
    }


def _is_ascii(text: str) -> bool:
    return all(ord(ch) < 128 for ch in text)


def _record_handwriting(status: str, start_ms: float, *, fallback: bool = False) -> None:
    duration_ms = (time.time() * 1000) - start_ms
    prometheus_metrics.record_handwriting_request(status, fallback=fallback)
    prometheus_metrics.record_handwriting_duration(duration_ms, status=status)


async def _call_autohanding(text: str, options: dict[str, Any]) -> bytes:
    from integrations.autohanding import client as autohanding_client
    from integrations.autohanding import constants

    return await autohanding_client.convert_text(
        text[: constants.MAX_TEXT_LENGTH],
        font_type=options["font_type"],
        paper_bg_type=options["paper_bg_type"],
        mistake_rate=options["mistake_rate"],
        messy_ratio=options["messy_ratio"],
        char_random=options["char_random"],
    )


async def _vectorize_handwriting_png(png_bytes: bytes) -> dict[str, Any]:
    from xiaozhi_drawing.svg_converter import SVGConverter

    converter = SVGConverter()
    return await converter.convert_bytes_to_svg(
        png_bytes,
        skeletonize=True,
        reorder_strokes=True,
        threshold_mode="auto",
        spur_length_threshold=10,
        min_stroke_length=5.0,
    )


def _build_local_fallback_params(text: str) -> dict[str, Any]:
    rendered = text_to_svg_path(text)
    return {
        "feed": DEFAULT_FEED,
        "path": rendered["path"],
        "source_capability": "handwriting",
        "text": text[:80],
        "preview_svg": rendered.get("preview_svg", ""),
        "backend": "lima-local",
    }


def _build_handwriting_run_params(svg_path: str, text: str, feed: int = DEFAULT_FEED) -> dict[str, Any]:
    rendered = render_svg_task(svg_path)
    return {
        "feed": feed,
        "path": rendered["path"],
        "source_capability": "handwriting",
        "text": text[:80],
        "preview_svg": rendered.get("preview_svg", ""),
    }


async def build_handwriting_params(params: dict[str, Any], _device_id: str) -> tuple[dict[str, Any], str | None]:
    """Build device run params from autohanding.com handwriting preview."""
    text = str(params.get("text", "")).strip()
    if not text:
        return {}, "empty handwriting text"

    start_ms = time.time() * 1000
    options = _handwriting_options(params)
    try:
        png_bytes = await _call_autohanding(text, options)
    except Exception as exc:
        if isinstance(exc, AutohandingRateLimitError):
            _record_handwriting("rate_limit", start_ms)
            return {}, f"autohanding rate limit: {exc}"
        _log.warning("autohanding failed for task mode, trying local fallback: %s", exc)
        if _is_ascii(text):
            _record_handwriting("fallback", start_ms, fallback=True)
            return _build_local_fallback_params(text), None
        _record_handwriting("failed", start_ms)
        return {}, f"autohanding error: {exc}"

    svg_result = await _vectorize_handwriting_png(png_bytes)
    if svg_result.get("status") != "success" or not svg_result.get("svg_path"):
        _record_handwriting("vectorization_failed", start_ms)
        return {}, svg_result.get("error") or "handwriting vectorization failed"

    _record_handwriting("success", start_ms)
    return _build_handwriting_run_params(str(svg_result["svg_path"]), text, _clamp_feed(params.get("feed"))), None


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
    user_feed = _clamp_feed(params.get("feed"))
    if _looks_like_svg_path(prompt):
        rendered = render_svg_task(prompt)
        return {
            "feed": user_feed,
            "path": rendered["path"],
            "source_capability": "draw_generated",
            "prompt": prompt,
            "preview_svg": rendered.get("preview_svg", ""),
        }, None

    provided_image_url = params.get("imageUrl") or params.get("image_url")
    result = await handle_device_draw(
        prompt,
        device_id=device_id,
        user_preferences=_draw_user_preferences(params),
        image_url=str(provided_image_url) if provided_image_url else None,
    )
    if result.get("status") != "success" or not result.get("svg_path"):
        error = str(result.get("error") or "draw generation failed")
        return {}, error

    rendered = render_svg_task(str(result["svg_path"]))
    run_params: dict[str, Any] = {
        "feed": user_feed,
        "path": rendered["path"],
        "source_capability": "draw_generated",
        "prompt": prompt,
        "preview_svg": rendered.get("preview_svg", ""),
    }
    returned_image_url = result.get("image_url") or provided_image_url
    if isinstance(returned_image_url, str) and returned_image_url:
        run_params["image_url"] = returned_image_url[:512]
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
            "feed": _clamp_feed(params.get("feed")),
            "path": rendered["path"],
            "source_capability": "write_text",
            "text": str(params.get("text", ""))[:80],
            "preview_svg": rendered.get("preview_svg", ""),
        }, None
    if capability == "draw_generated":
        prompt = str(params.get("prompt", ""))[:120]
        return await build_draw_generated_params(prompt, device_id, params)
    if capability == "handwriting":
        return await build_handwriting_params(params, device_id)
    if capability in CONTROL_CAPABILITIES:
        return {"source_capability": capability}, None
    return {"feed": DEFAULT_FEED, "path": [safe_point(0, 0, 0)], "source_capability": capability}, None
