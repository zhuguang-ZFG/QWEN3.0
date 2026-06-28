"""Image generation endpoint.

Primary: xmiaom gpt-image-2 (OpenAI-compatible chat completion returning markdown image link).
Fallback: Pollinations.ai URL builder (kept for zero-config environments and chat UI).
"""

import base64
import json
import logging
import os
import re
import time
import urllib.parse

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from access_guard import require_private_api_key
from config import backend_config
from observability import prometheus_metrics as _prom_metrics
from routes.images_cache import get_cached_image, set_cached_image, should_skip_cache
from routes.json_body import read_json_object

router = APIRouter()
_log = logging.getLogger(__name__)

IMAGE_BACKEND = "xmiaom_gpt_image_2"


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


_OPENAI_IMAGE_TIMEOUT = int(os.environ.get("LIMA_OPENAI_IMAGE_TIMEOUT_SECONDS", "120"))


def _map_to_openai_image_size(size: str) -> str:
    """Map free-form widthxheight to an OpenAI-compatible image size."""
    parts = size.lower().split("x")
    if len(parts) != 2:
        return "1024x1024"
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError:
        return "1024x1024"
    if width > height:
        return "1792x1024"
    if height > width:
        return "1024x1792"
    return "1024x1024"


def _extract_openai_image_url(item: dict) -> str:
    """Return a usable URL from an OpenAI images/generations result item."""
    url = item.get("url")
    if url:
        return url
    b64 = item.get("b64_json")
    if b64:
        return f"data:image/png;base64,{b64}"
    return ""


async def _generate_via_openai_image_endpoint(
    endpoint: str,
    api_key: str,
    model: str,
    prompt: str,
    size: str,
    n: int,
) -> list[dict]:
    """Call an OpenAI-compatible /v1/images/generations endpoint."""
    if not api_key:
        return []
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": prompt,
        "n": min(max(n, 1), 10),
        "size": _map_to_openai_image_size(size),
    }
    try:
        async with httpx.AsyncClient(timeout=_OPENAI_IMAGE_TIMEOUT) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        status = getattr(exc, "response_status_code", None) or getattr(
            getattr(exc, "response", None), "status_code", None
        )
        _log.warning(
            "openai image generation failed: endpoint=%s status=%s error=%s",
            endpoint,
            status,
            str(exc)[:200],
        )
        return []

    items: list[dict] = []
    for entry in data.get("data", []):
        url = _extract_openai_image_url(entry)
        if url:
            items.append({"url": url})
    if not items:
        _log.warning("openai image generation returned no usable url/b64_json")
    return items


async def _generate_via_freetheai(prompt: str, size: str, n: int) -> list[dict]:
    """FreeTheAi image generation fallback (OpenAI-compatible)."""
    return await _generate_via_openai_image_endpoint(
        "https://api.freetheai.xyz/v1/images/generations",
        backend_config.FREETHEAI_API_KEY,
        "img/gpt-image-2",
        prompt,
        size,
        n,
    )


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
        cached = get_cached_image(enhanced_prompt, size)
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
        data_items = await _generate_via_pollinations(enhanced_prompt, size, n)
        backend = "pollinations"
    duration_ms = int((time.time() - started) * 1000)

    if data_items:
        set_cached_image(enhanced_prompt, size, data_items, backend)

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
        prompt, img_req.size, img_req.n, skip_cache=should_skip_cache(request)
    )
    urls = [{"url": item["url"]} for item in data_items]
    _record_image_request(img_req.prompt[:80], backend, duration_ms, client_ip)

    return JSONResponse(
        {
            "created": int(time.time()),
            "data": urls,
        }
    )
