"""Device-app authenticated handwriting generation routes.

Uses autohanding.com free preview API to turn text into a handwritten page,
then converts the raster result into an SVG path suitable for the plotter.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from device_gateway import path_pipeline
from device_gateway.task_draw_params import build_handwriting_params
from device_logic.auth import authorize
from device_logic.http import err, read_body
from integrations.autohanding import client as autohanding_client
from integrations.autohanding import constants
from observability import prometheus_metrics
from xiaozhi_drawing.svg_converter import SVGConverter

router = APIRouter(prefix="/device/v1/app", tags=["handwriting"])
_log = logging.getLogger(__name__)

_ENABLED = os.environ.get("LIMA_HANDWRITING_ENABLED", "1") == "1"


class HandwritingRequest(BaseModel):
    text: str = Field(min_length=1, max_length=constants.MAX_TEXT_LENGTH)
    font_type: str = constants.DEFAULT_FONT_TYPE
    paper_bg_type: str = constants.DEFAULT_PAPER_BG_TYPE
    mistake_rate: int = Field(default=constants.DEFAULT_MISTAKE_RATE, ge=0, le=100)
    messy_ratio: int = Field(default=constants.DEFAULT_MESSY_RATIO, ge=0, le=100)
    char_random: int = Field(default=constants.DEFAULT_CHAR_RANDOM, ge=0, le=100)
    mode: str = "svg"


async def _load_request(request: Request, authorization: str) -> tuple[HandwritingRequest | None, JSONResponse | None]:
    if not _ENABLED:
        return None, err(503, "handwriting service disabled", 503)

    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return None, account

    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return None, body

    try:
        return HandwritingRequest(**body), None
    except ValidationError:
        return None, err(400, "invalid handwriting request", 400)


def _is_local_fallback_supported(text: str) -> bool:
    """The built-in stroke font only covers ASCII; Chinese needs autohanding."""
    return all(ord(ch) < 128 for ch in text)


def _fallback_svg_result(text: str) -> dict[str, Any] | JSONResponse:
    """Use the deterministic stroke font when autohanding is unavailable."""
    if not _is_local_fallback_supported(text):
        return err(502, "autohanding unavailable and local font does not cover this text", 502)
    try:
        return path_pipeline.text_to_svg_path(text)
    except Exception as exc:
        _log.warning("local handwriting fallback failed: %s", exc)
        return err(502, "handwriting fallback failed", 502)


async def _generate_svg(req: HandwritingRequest) -> dict[str, Any] | JSONResponse:
    start_ms = time.time() * 1000
    fallback = False
    try:
        png_bytes = await autohanding_client.convert_text(
            req.text,
            font_type=req.font_type,
            paper_bg_type=req.paper_bg_type,
            mistake_rate=req.mistake_rate,
            messy_ratio=req.messy_ratio,
            char_random=req.char_random,
        )
    except autohanding_client.AutohandingRateLimitError:
        prometheus_metrics.record_handwriting_request("rate_limit")
        prometheus_metrics.record_handwriting_duration((time.time() * 1000) - start_ms, status="rate_limit")
        return err(429, "autohanding rate limit, please retry later", 429)
    except autohanding_client.AutohandingClientError as exc:
        _log.warning("autohanding request failed after retries: %s", exc)
        svg_result = _fallback_svg_result(req.text)
        fallback = isinstance(svg_result, dict) and svg_result.get("backend") == "lima-local"
        status = "fallback" if fallback else "failed"
        prometheus_metrics.record_handwriting_request(status, fallback=fallback)
        prometheus_metrics.record_handwriting_duration((time.time() * 1000) - start_ms, status=status)
        if isinstance(svg_result, JSONResponse):
            return svg_result
        return svg_result

    converter = SVGConverter()
    svg_result = await converter.convert_bytes_to_svg(
        png_bytes,
        skeletonize=True,
        reorder_strokes=True,
        threshold_mode="auto",
        spur_length_threshold=10,
        min_stroke_length=5.0,
    )
    if svg_result["status"] != "success" or not svg_result.get("svg_path"):
        prometheus_metrics.record_handwriting_request("vectorization_failed")
        prometheus_metrics.record_handwriting_duration((time.time() * 1000) - start_ms, status="vectorization_failed")
        return err(502, f"handwriting vectorization failed: {svg_result.get('error')}", 502)

    prometheus_metrics.record_handwriting_request("success")
    prometheus_metrics.record_handwriting_duration((time.time() * 1000) - start_ms, status="success")
    return svg_result


def _build_response(svg_result: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        {
            "created": int(time.time()),
            "data": [
                {
                    "svg_path": svg_result["svg_path"],
                    "width": svg_result["width"],
                    "height": svg_result["height"],
                    "backend": svg_result.get("backend", "autohanding"),
                }
            ],
        }
    )


async def _build_task_response(req: HandwritingRequest) -> JSONResponse:
    params, error = await build_handwriting_params(req.model_dump(), "")
    if error:
        return err(502, error, 502)
    return JSONResponse({"created": int(time.time()), "data": [params]})


def _build_options_response() -> JSONResponse:
    return JSONResponse(
        {
            "fonts": constants.FONT_OPTIONS,
            "papers": constants.PAPER_BG_OPTIONS,
            "defaults": {
                "font_type": constants.DEFAULT_FONT_TYPE,
                "paper_bg_type": constants.DEFAULT_PAPER_BG_TYPE,
                "mistake_rate": constants.DEFAULT_MISTAKE_RATE,
                "messy_ratio": constants.DEFAULT_MESSY_RATIO,
                "char_random": constants.DEFAULT_CHAR_RANDOM,
            },
            "max_text_length": constants.MAX_TEXT_LENGTH,
        }
    )


@router.get("/handwriting/options")
async def device_app_handwriting_options(authorization: str = Header(default="")) -> JSONResponse:
    """Return available fonts, papers and defaults for the handwriting preview."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    return _build_options_response()


@router.post("/handwriting")
async def device_app_handwriting(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """Generate a handwritten page from text and return an SVG path or task."""
    req, error_response = await _load_request(request, authorization)
    if error_response is not None or req is None:
        return error_response or err(500, "unknown error", 500)

    if req.mode == "task":
        return await _build_task_response(req)

    svg_result = await _generate_svg(req)
    if isinstance(svg_result, JSONResponse):
        return svg_result

    return _build_response(svg_result)
