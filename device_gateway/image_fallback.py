"""Image fallback for device draw: reuse /v1/images multi-backend chain.

当 DashScope 生图失败时，复用 routes.images._generate_image_urls 的多后端降级链路
（xmiaom→agnes→siliconflow→zhipu→freetheai→pollinations），消除写字机生图单点风险。

从 device_draw_handler.py 拆出（保持单文件 ≤300 行约束）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from routes.images import _generate_image_urls

logger = logging.getLogger(__name__)


async def generate_via_image_fallback(prompt: str, size: str, device_id: Optional[str]) -> Dict[str, Any]:
    """DashScope 失败时的降级：复用 /v1/images 的多后端链路。

    返回结构与 DashScopeImageClient.generate() 一致（status/images/task_id/error），
    下游 device_draw_handler 无需改动。
    """
    # size 格式适配：DashScope 用 '*' (1024*1024)，images.py 用 'x' (1024x1024)
    normalized_size = size.replace("*", "x")
    try:
        data_items, _backend, _duration = await _generate_image_urls(
            prompt, normalized_size, 1, {}, skip_cache=False
        )
        if data_items:
            return {
                "status": "success",
                "images": [{"url": it["url"]} for it in data_items],
                "task_id": "",
                "error": None,
            }
        return {"status": "failed", "images": [], "task_id": "", "error": "image fallback returned no urls"}
    except Exception as e:
        logger.warning(f"Image fallback failed for device {device_id}: {e}")
        return {"status": "failed", "images": [], "task_id": "", "error": str(e)}
