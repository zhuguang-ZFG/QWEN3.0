"""Handwriting parameter builders for device task creation."""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from integrations.autohanding.client import AutohandingRateLimitError
from observability import prometheus_metrics

from .path_pipeline import render_svg_task, text_to_svg_path
from .path_validator import MAX_FEED, MIN_FEED
from .safety import DEFAULT_FEED

_log = logging.getLogger(__name__)


def _clamp_feed(raw: Any, default: int = DEFAULT_FEED) -> int:
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(val):
        return default
    return int(max(MIN_FEED, min(MAX_FEED, val)))


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


def _build_local_fallback_params(text: str, feed: int = DEFAULT_FEED) -> dict[str, Any]:
    rendered = text_to_svg_path(text)
    return {
        "feed": feed,
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
            return _build_local_fallback_params(text, _clamp_feed(params.get("feed"))), None
        _record_handwriting("failed", start_ms)
        return {}, f"autohanding error: {exc}"

    svg_result = await _vectorize_handwriting_png(png_bytes)
    if svg_result.get("status") != "success" or not svg_result.get("svg_path"):
        _record_handwriting("vectorization_failed", start_ms)
        return {}, svg_result.get("error") or "handwriting vectorization failed"

    _record_handwriting("success", start_ms)
    return _build_handwriting_run_params(str(svg_result["svg_path"]), text, _clamp_feed(params.get("feed"))), None
