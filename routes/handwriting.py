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

from device_gateway.task_draw_params import build_handwriting_params
from device_logic.auth import authorize
from device_logic.http import err, read_body
from integrations.autohanding import client as autohanding_client
from integrations.autohanding import constants
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


async def _generate_svg(req: HandwritingRequest) -> dict[str, Any] | JSONResponse:
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
        return err(429, "autohanding rate limit, please retry later", 429)
    except autohanding_client.AutohandingClientError as exc:
        _log.warning("autohanding request failed: %s", exc)
        return err(502, "autohanding service unavailable", 502)

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
        return err(502, f"handwriting vectorization failed: {svg_result.get('error')}", 502)
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
                    "backend": "autohanding",
                }
            ],
        }
    )


async def _build_task_response(req: HandwritingRequest) -> JSONResponse:
    params, error = await build_handwriting_params(req.model_dump(), "")
    if error:
        return err(502, error, 502)
    return JSONResponse({"created": int(time.time()), "data": [params]})


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
