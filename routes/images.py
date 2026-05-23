"""Image generation via Pollinations.ai."""

import re
import time
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from access_guard import require_private_api_key

router = APIRouter()


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
    return (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width={width}&height={height}&nologo=true"
    )


_record_request_fn = None


def inject_record_request(fn):
    global _record_request_fn
    _record_request_fn = fn


@router.post("/v1/images/generations", dependencies=[Depends(require_private_api_key)])
async def image_generations(request: Request):
    """OpenAI-compatible image generation endpoint using Pollinations.ai."""
    body = await request.json()
    img_req = ImageRequest(**body)
    prompt = img_req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Empty prompt")

    if re.search(r"[\u4e00-\u9fff]", prompt):
        prompt = f"high quality, detailed, {prompt}"

    urls = [
        {"url": build_pollinations_url(prompt, img_req.size)}
        for _ in range(img_req.n)
    ]

    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
    )
    if _record_request_fn:
        _record_request_fn(
            img_req.prompt[:80],
            "pollinations",
            "image_generation",
            0,
            True,
            client_ip=client_ip,
        )

    return JSONResponse({
        "created": int(time.time()),
        "data": urls,
    })
