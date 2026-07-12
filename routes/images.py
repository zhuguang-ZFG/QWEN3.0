"""Image generation endpoint.

Primary: xmiaom gpt-image-2 (OpenAI-compatible chat completion returning markdown image link).
Fallbacks (OpenAI-compatible /v1/images/generations): Agnes (free) → SiliconFlow (FLUX) → Zhipu CogView → Baidu Qianfan → Tencent Hunyuan → Volcengine Doubao → FreeTheAi.
Final fallback: Pollinations.ai URL builder (zero-config).
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from access_guard import require_private_api_key
from device_gateway.image_url_validation import validate_image_url
from observability import prometheus_metrics as _prom_metrics
from routes.images_backends import (
    IMAGE_BACKEND,
    _generate_via_agnes,
    _generate_via_baidu,
    _generate_via_dashscope_i2i,
    _generate_via_freetheai,
    _generate_via_siliconflow,
    _generate_via_tencent,
    _generate_via_volcengine,
    _generate_via_xmiaom,
    _generate_via_zhipu,
)
from routes.images_cache import get_cached_image, set_cached_image, should_skip_cache
from routes.images_pollinations import build_variant, generate_pollinations_urls
from routes.json_body import read_json_object

router = APIRouter()
_log = logging.getLogger(__name__)

# Backend chain for _generate_image_urls. Each entry is (backend_name, coroutine).
# The lambdas unify signatures so the main loop can call each with (prompt, size, n).
_IMAGE_BACKENDS: list[tuple[str, Callable[..., Awaitable[list[dict]]]]] = [
    (IMAGE_BACKEND, lambda prompt, size, n: _generate_via_xmiaom(prompt, size)),
    ("agnes", _generate_via_agnes),
    ("siliconflow", _generate_via_siliconflow),
    ("zhipu_cogview", _generate_via_zhipu),
    ("baidu_qianfan", _generate_via_baidu),
    ("tencent_hunyuan", _generate_via_tencent),
    ("volcengine_doubao", _generate_via_volcengine),
    ("freetheai", _generate_via_freetheai),
]


class ImageRequest(BaseModel):
    prompt: str = Field(max_length=4000)
    model: str = "lima-image"
    size: str = Field(default="1024x1024", pattern=r"^\d{1,4}x\d{1,4}$")
    n: int = Field(default=1, ge=1, le=10)
    seed: int | None = Field(default=None, ge=-1, le=2147483647)
    negative_prompt: str | None = Field(default=None, max_length=4000)
    image_url: str | None = Field(default=None, description="Optional reference image for image-to-image generation")
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


async def _try_i2i_backend(prompt: str, image_url: str, size: str, n: int) -> tuple[list[dict], str]:
    # SEC-04: never forward private/non-allowlisted hosts to DashScope.
    validated, url_err = validate_image_url(image_url)
    if url_err or validated is None:
        raise ValueError(url_err or "invalid image_url")
    data_items = await _generate_via_dashscope_i2i(prompt, validated, size, n)
    return (data_items, "dashscope_i2i") if data_items else ([], "")


async def _try_image_backends(prompt: str, size: str, n: int, options: dict) -> tuple[list[dict], str]:
    for backend_name, generator in _IMAGE_BACKENDS:
        data_items = await generator(prompt, size, n)
        if data_items:
            return data_items, backend_name
    data_items = await generate_pollinations_urls(prompt, size, n, options)
    return data_items, "pollinations"


async def _generate_image_urls(
    prompt: str,
    size: str,
    n: int,
    options: dict,
    *,
    skip_cache: bool = False,
    image_url: str | None = None,
) -> tuple[list[dict], str, int]:
    """Generate image URLs and return (items, backend, duration_ms)."""
    enhanced_prompt = _apply_default_enhancement(prompt)
    variant = build_variant(options)

    if not skip_cache and not image_url:
        cached = get_cached_image(enhanced_prompt, size, n, variant)
        if cached is not None:
            data_items, backend = cached
            return data_items, backend, 0
        _prom_metrics.record_image_cache_lookup("miss")

    started = time.time()
    data_items: list[dict] = []
    backend = ""
    if image_url:
        data_items, backend = await _try_i2i_backend(enhanced_prompt, image_url, size, n)
    if not data_items:
        data_items, backend = await _try_image_backends(enhanced_prompt, size, n, options)

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
        # AUDIT-6-A2：error 字段用对象形式，与 chat_endpoints 的 {"error":{"message":...}} 一致
        return JSONResponse(
            {"error": {"message": "invalid image request", "type": "invalid_request_error"}}, status_code=400
        )
    prompt = img_req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Empty prompt")

    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else ""
    )

    options = _build_pollinations_options(img_req)
    try:
        data_items, backend, duration_ms = await _generate_image_urls(
            prompt,
            img_req.size,
            img_req.n,
            options,
            skip_cache=should_skip_cache(request),
            image_url=img_req.image_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    urls = [{"url": item["url"]} for item in data_items]
    _record_image_request(img_req.prompt[:80], backend, duration_ms, client_ip)

    return JSONResponse(
        {
            "created": int(time.time()),
            "data": urls,
        }
    )
