"""Image generation endpoint.

Primary: xmiaom gpt-image-2 (OpenAI-compatible chat completion returning markdown image link).
Fallback: Pollinations.ai URL builder (kept for zero-config environments and chat UI).
"""

import json
import logging
import os
import re
import time
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from access_guard import require_private_api_key
from observability import prometheus_metrics as _prom_metrics
from routes.json_body import read_json_object

router = APIRouter()
_log = logging.getLogger(__name__)

IMAGE_BACKEND = "xmiaom_gpt_image_2"

_IMAGE_CACHE_TTL_SECONDS = int(os.environ.get("LIMA_IMAGE_CACHE_TTL_SECONDS", "3600"))
_IMAGE_CACHE_MAX_ENTRIES = int(os.environ.get("LIMA_IMAGE_CACHE_MAX_ENTRIES", "100"))
_image_cache: dict[tuple[str, str], tuple[list[dict], str, float]] = {}


def _image_cache_key(prompt: str, size: str) -> tuple[str, str]:
    return (prompt.strip().lower(), size)


def _get_cached_image(prompt: str, size: str) -> tuple[list[dict], str] | None:
    if _IMAGE_CACHE_TTL_SECONDS <= 0:
        return None
    key = _image_cache_key(prompt, size)
    entry = _image_cache.get(key)
    if not entry:
        return None
    data_items, backend, cached_at = entry
    if time.time() - cached_at > _IMAGE_CACHE_TTL_SECONDS:
        _image_cache.pop(key, None)
        return None
    _log.info("image cache hit for prompt=%s size=%s backend=%s", prompt[:40], size, backend)
    _prom_metrics.record_image_cache_lookup("hit")
    return data_items, backend


def _set_cached_image(prompt: str, size: str, data_items: list[dict], backend: str) -> None:
    if _IMAGE_CACHE_TTL_SECONDS <= 0:
        return
    key = _image_cache_key(prompt, size)
    if len(_image_cache) >= _IMAGE_CACHE_MAX_ENTRIES:
        oldest = min(_image_cache, key=lambda k: _image_cache[k][2])
        _image_cache.pop(oldest, None)
    _image_cache[key] = (data_items, backend, time.time())
    _log.info("image cache set for prompt=%s size=%s backend=%s entries=%d", prompt[:40], size, backend, len(_image_cache))
    _prom_metrics.record_image_cache_entries(len(_image_cache))


def _should_skip_cache(request: Request) -> bool:
    return request.headers.get("x-skip-cache", "").strip().lower() in ("1", "true", "yes")


class ImageRequest(BaseModel):
    prompt: str
    model: str = "lima-image"
    size: str = Field(default="1024x1024", pattern=r"^\d{1,4}x\d{1,4}$")
    n: int = Field(default=1, ge=1, le=10)

    @field_validator("size")
    @classmethod
    def reject_oversized_dimensions(cls, value: str) -> str:
        width, height = (int(part) for part in value.split("x"))
        if width > 2048 or height > 2048:
            raise ValueError("image dimensions must be at most 2048")
        return value


def build_pollinations_url(prompt: str, size: str = "1024x1024") -> str:
    """Build Pollinations.ai image URL from prompt and size."""
    parts = size.split("x")
    width = int(parts[0]) if len(parts) == 2 else 1024
    height = int(parts[1]) if len(parts) == 2 else 1024
    encoded_prompt = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"


_record_request_fn = None


def inject_record_request(fn):
    global _record_request_fn
    _record_request_fn = fn


def _extract_image_url(content: str) -> str:
    """Extract the first https:// image URL from assistant markdown content."""
    if not content:
        return ""
    match = re.search(r"https?://[^\s\)\"\]\)]+\.(?:png|jpe?g|gif|webp|bmp)", content, re.IGNORECASE)
    return match.group(0) if match else ""


def _build_xmiaom_payload(prompt: str, size: str = "1024x1024") -> bytes:
    """Build a minimal chat completion payload for gpt-image-2."""
    return json.dumps(
        {
            "model": "gpt-image-2",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
        },
        ensure_ascii=False,
    ).encode()


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


async def _generate_via_xmiaom(prompt: str, size: str) -> list[dict]:
    """Call xmiaom gpt-image-2 and return image URL objects."""
    try:
        from http_async import call_raw_async
    except ImportError as exc:
        _log.warning("http_async not available; xmiaom image generation disabled: %s", exc)
        return []

    payload = _build_xmiaom_payload(prompt, size)
    started = time.time()
    try:
        data = await call_raw_async(IMAGE_BACKEND, payload)
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        _log.warning(
            "xmiaom image generation failed: %s (status=%s, msg=%s)",
            type(exc).__name__,
            status,
            str(exc)[:200],
        )
        return []

    content = ""
    try:
        content = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        _log.warning("xmiaom image generation returned unexpected shape: %s", type(data).__name__)
        return []

    image_url = _extract_image_url(content)
    if not image_url:
        _log.warning(
            "xmiaom image generation returned no image URL in content: %s",
            content[:200],
        )
        return []

    duration_ms = int((time.time() - started) * 1000)
    return [{"url": image_url, "backend": IMAGE_BACKEND, "latency_ms": duration_ms}]


async def _generate_via_pollinations(prompt: str, size: str, n: int) -> list[dict]:
    """Fallback image URL generator using Pollinations.ai."""
    return [{"url": build_pollinations_url(prompt, size)} for _ in range(n)]


async def _generate_image_urls(
    prompt: str, size: str, n: int, *, skip_cache: bool = False
) -> tuple[list[dict], str, int]:
    """Generate image URLs and return (items, backend, duration_ms).

    Caches successful results by (prompt, size) to avoid redundant API calls.
    """
    enhanced_prompt = prompt
    if re.search(r"[\u4e00-\u9fff]", enhanced_prompt):
        enhanced_prompt = f"high quality, detailed, {enhanced_prompt}"

    if not skip_cache:
        cached = _get_cached_image(enhanced_prompt, size)
        if cached is not None:
            data_items, backend = cached
            return data_items, backend, 0
        _prom_metrics.record_image_cache_lookup("miss")

    data_items = await _generate_via_xmiaom(enhanced_prompt, size)
    backend = IMAGE_BACKEND
    duration_ms = data_items[0].get("latency_ms", 0) if data_items else 0
    if not data_items:
        data_items = await _generate_via_pollinations(enhanced_prompt, size, n)
        backend = "pollinations"
        duration_ms = 0

    if data_items:
        _set_cached_image(enhanced_prompt, size, data_items, backend)

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

    data_items, backend, duration_ms = await _generate_image_urls(
        prompt, img_req.size, img_req.n, skip_cache=_should_skip_cache(request)
    )
    urls = [{"url": item["url"]} for item in data_items]
    _record_image_request(img_req.prompt[:80], backend, duration_ms, client_ip)

    return JSONResponse(
        {
            "created": int(time.time()),
            "data": urls,
        }
    )
