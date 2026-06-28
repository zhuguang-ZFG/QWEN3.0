"""Device-app authenticated image generation routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.auth import authorize
from device_logic.http import err, read_body
from routes.images import ImageRequest, _generate_image_urls
from routes.images_cache import should_skip_cache

router = APIRouter(prefix="/device/v1/app", tags=["device-app-images"])

# 对外统一品牌名，隐藏真实生图后端（xmiaom/FreeTheAi/Pollinations 等）。
# 真实后端名仅用于内部监控（_record_image_request / Prometheus），不外泄给客户端。
PUBLIC_IMAGE_BACKEND_LABEL = "LiMa 生图"


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

    options = {
        "model": img_req.model,
        "seed": img_req.seed,
        "negative_prompt": img_req.negative_prompt,
        "nologo": img_req.nologo,
        "private": img_req.private,
        "enhance": img_req.enhance,
        "safe": img_req.safe,
    }
    data_items, backend, _duration_ms = await _generate_image_urls(
        prompt, img_req.size, img_req.n, options, skip_cache=should_skip_cache(request)
    )
    urls = [{"url": item["url"]} for item in data_items]

    # 真实 backend 仅保留在函数局部（可用于内部监控），对外响应统一返回品牌标签。
    _ = backend

    return JSONResponse(
        {
            "created": int(time.time()),
            "data": urls,
            "backend": PUBLIC_IMAGE_BACKEND_LABEL,
        }
    )
