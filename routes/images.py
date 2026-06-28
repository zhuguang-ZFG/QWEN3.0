"""Image generation endpoint.

Primary: xmiaom gpt-image-2 (OpenAI-compatible chat completion returning markdown image link).
Fallback: Pollinations.ai URL builder (kept for zero-config environments and chat UI).
"""

import json
import logging
import re
import time
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from access_guard import require_private_api_key
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
        _log.warning("xmiaom image generation failed: %s", type(exc).__name__)
        return []

    content = ""
    try:
        content = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        _log.warning("xmiaom image generation returned unexpected shape: %s", type(data).__name__)
        return []

    image_url = _extract_image_url(content)
    if not image_url:
        _log.warning("xmiaom image generation returned no image URL in content")
        return []

    duration_ms = int((time.time() - started) * 1000)
    return [{"url": image_url, "backend": IMAGE_BACKEND, "latency_ms": duration_ms}]


async def _generate_via_pollinations(prompt: str, size: str, n: int) -> list[dict]:
    """Fallback image URL generator using Pollinations.ai."""
    return [{"url": build_pollinations_url(prompt, size)} for _ in range(n)]


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

    if re.search(r"[\u4e00-\u9fff]", prompt):
        prompt = f"high quality, detailed, {prompt}"

    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else ""
    )

    data_items = await _generate_via_xmiaom(prompt, img_req.size)
    backend = IMAGE_BACKEND
    duration_ms = data_items[0].get("latency_ms", 0) if data_items else 0
    if not data_items:
        data_items = await _generate_via_pollinations(prompt, img_req.size, img_req.n)
        backend = "pollinations"
        duration_ms = 0

    urls = [{"url": item["url"]} for item in data_items]
    _record_image_request(img_req.prompt[:80], backend, duration_ms, client_ip)

    return JSONResponse(
        {
            "created": int(time.time()),
            "data": urls,
        }
    )
