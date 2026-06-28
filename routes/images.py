"""Image generation endpoint.

Primary: xmiaom gpt-image-2 (OpenAI-compatible chat completion returning markdown image link).
Fallback: FreeTheAi (OpenAI-compatible /v1/images/generations).
Final fallback: Pollinations.ai URL builder (zero-config).
"""

from __future__ import annotations

import logging
import os
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from access_guard import require_private_api_key
from observability import prometheus_metrics as _prom_metrics
from routes.images_backends import IMAGE_BACKEND, _generate_via_freetheai, _generate_via_xmiaom
from routes.images_cache import get_cached_image, set_cached_image, should_skip_cache
from routes.images_pollinations import build_variant, generate_pollinations_urls
from routes.json_body import read_json_object

router = APIRouter()
_log = logging.getLogger(__name__)


class ImageRequest(BaseModel):
    prompt: str
    model: str = "lima-image"
    size: str = Field(default="1024x1024", pattern=r"^\d{1,4}x\d{1,4}$")
    n: int = Field(default=1, ge=1, le=10)
    seed: int | None = Field(default=None, ge=-1, le=2147483647)
    negative_prompt: str | None = None
    nologo: bool = True
    private: bool = False
    enhance: bool = False
    safe: bool = False

    @field_validator("size")
    @classmethod
    def reject_oversized_dimensions(cls, value: str) -> str:
        width, height = (int(part) for part in value.split("x"))
        if width > 2048 or height > 2048:
            raise ValueError("image dimensions must be at most 2048")
        return value


_record_request_fn = None


def inject_record_request(fn):
    global _record_request_fn
    _record_request_fn = fn


def _record_image_request(prompt: str, backend: str, duration_ms: int, client_ip: str) -> None:
    if _record_request_fn:
        _record_request_fn(
            prompt[:80],
            backend,
            "image_generation",
            duration_ms,
            True,
            client_ip=client_ip,
        )


def _apply_default_enhancement(prompt: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", prompt):
        return f"high quality, detailed, {prompt}"
    return prompt


def _build_pollinations_options(img_req: ImageRequest) -> dict:
    return {
        "model": img_req.model,
        "seed": img_req.seed,
        "negative_prompt": img_req.negative_prompt,
        "nologo": img_req.nologo,
        "private": img_req.private,
        "enhance": img_req.enhance,
        "safe": img_req.safe,
    }


async def _generate_image_urls(
    prompt: str,
    size: str,
    n: int,
    options: dict,
    *,
    skip_cache: bool = False,
) -> tuple[list[dict], str, int]:
    """Generate image URLs and return (items, backend, duration_ms)."""
    enhanced_prompt = _apply_default_enhancement(prompt)
    variant = build_variant(options)

    if not skip_cache:
        cached = get_cached_image(enhanced_prompt, size, n, variant)
        if cached is not None:
            data_items, backend = cached
            return data_items, backend, 0
        _prom_metrics.record_image_cache_lookup("miss")

    started = time.time()
    data_items = await _generate_via_xmiaom(enhanced_prompt, size)
    backend = IMAGE_BACKEND
    if not data_items:
        data_items = await _generate_via_freetheai(enhanced_prompt, size, n)
        backend = "freetheai"
    if not data_items:
        data_items = await generate_pollinations_urls(enhanced_prompt, size, n, options)
        backend = "pollinations"
    duration_ms = int((time.time() - started) * 1000)

    if data_items:
        set_cached_image(enhanced_prompt, size, n, variant, data_items, backend)

    _prom_metrics.record_image_request(backend)
    return data_items, backend, duration_ms


@router.post("/v1/images/generations", dependencies=[Depends(require_private_api_key)])
async def image_generations(request: Request):
    """OpenAI-compatible image generation endpoint."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    try:
        img_req = ImageRequest(**body)
    except ValidationError:
        return JSONResponse({"error": "invalid image request"}, status_code=400)
    prompt = img_req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Empty prompt")

    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else ""
    )

    options = _build_pollinations_options(img_req)
    data_items, backend, duration_ms = await _generate_image_urls(
        prompt, img_req.size, img_req.n, options, skip_cache=should_skip_cache(request)
    )
    urls = [{"url": item["url"]} for item in data_items]
    _record_image_request(img_req.prompt[:80], backend, duration_ms, client_ip)

    return JSONResponse(
        {
            "created": int(time.time()),
            "data": urls,
        }
    )
