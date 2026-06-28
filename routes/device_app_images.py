"""Device-app authenticated image generation routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.auth import authorize
from device_logic.http import err, read_body
from routes.images import ImageRequest, _generate_image_urls

router = APIRouter(prefix="/device/v1/app", tags=["device-app-images"])


@router.post("/images/generations")
async def device_app_image_generations(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """Generate images using the same backend as /v1/images/generations but with device-app auth."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body

    try:
        img_req = ImageRequest(**body)
    except Exception:
        return err(400, "invalid image request", 400)

    prompt = img_req.prompt.strip()
    if not prompt:
        return err(400, "empty prompt", 400)

    data_items, backend, _duration_ms = await _generate_image_urls(prompt, img_req.size, img_req.n)
    urls = [{"url": item["url"]} for item in data_items]

    return JSONResponse(
        {
            "created": int(time.time()),
            "data": urls,
            "backend": backend,
        }
    )
