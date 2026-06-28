"""Backend-specific image generators (xmiaom, FreeTheAi, Agnes, SiliconFlow, Zhipu, Baidu, Tencent, Volcengine)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time

import httpx

from config import backend_config

_log = logging.getLogger(__name__)

IMAGE_BACKEND = "xmiaom_gpt_image_2"

_OPENAI_IMAGE_TIMEOUT = int(os.environ.get("LIMA_OPENAI_IMAGE_TIMEOUT_SECONDS", "120"))
_XMIAOM_IMAGE_TIMEOUT = int(os.environ.get("LIMA_XMIAOM_IMAGE_TIMEOUT_SECONDS", "30"))


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


def _extract_image_url(content: str) -> str:
    """Extract the first https:// image URL from assistant markdown content."""
    if not content:
        return ""
    match = re.search(r"https?://[^\s\)\"\]\)]+\.(?:png|jpe?g|gif|webp|bmp)", content, re.IGNORECASE)
    return match.group(0) if match else ""


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


async def _generate_via_agnes(prompt: str, size: str, n: int) -> list[dict]:
    """Agnes AI image generation (OpenAI-compatible, free, agnes-image-2.0-flash)."""
    return await _generate_via_openai_image_endpoint(
        "https://apihub.agnes-ai.com/v1/images/generations",
        backend_config.AGNES_AI_API_KEY,
        "agnes-image-2.0-flash",
        prompt,
        size,
        n,
    )


async def _generate_via_siliconflow(prompt: str, size: str, n: int) -> list[dict]:
    """SiliconFlow image generation (FLUX.1-schnell, OpenAI-compatible)."""
    return await _generate_via_openai_image_endpoint(
        "https://api.siliconflow.cn/v1/images/generations",
        backend_config.SILICONFLOW_API_KEY,
        "black-forest-labs/FLUX.1-schnell",
        prompt,
        size,
        n,
    )


async def _generate_via_zhipu(prompt: str, size: str, n: int) -> list[dict]:
    """Zhipu CogView image generation (OpenAI-compatible at /paas/v4, cogview-4-flash)."""
    return await _generate_via_openai_image_endpoint(
        "https://open.bigmodel.cn/api/paas/v4/images/generations",
        backend_config.ZHIPU_API_KEY,
        "cogview-4-flash",
        prompt,
        size,
        n,
    )


async def _generate_via_baidu(prompt: str, size: str, n: int) -> list[dict]:
    """Baidu Qianfan image generation (OpenAI-compatible at /v2, stable-diffusion-xl)."""
    return await _generate_via_openai_image_endpoint(
        "https://qianfan.baidubce.com/v2/images/generations",
        backend_config.BAIDU_API_KEY,
        "stable-diffusion-xl",
        prompt,
        size,
        n,
    )


async def _generate_via_tencent(prompt: str, size: str, n: int) -> list[dict]:
    """Tencent Hunyuan image generation (OpenAI-compatible at api.cloudai.tencent.com)."""
    return await _generate_via_openai_image_endpoint(
        "https://api.cloudai.tencent.com/v1/images/generations",
        backend_config.TENCENT_API_KEY,
        "hunyuan-image",
        prompt,
        size,
        n,
    )


async def _generate_via_volcengine(prompt: str, size: str, n: int) -> list[dict]:
    """Volcengine Doubao Seedream image generation (OpenAI-compatible at ark /api/v3).

    Note: Volcengine Ark 生图 model 参数实际需用接入点 ID (ep-xxx) 或特定模型 ID；
    此处用模型名占位，部署时若需 ep-xxx 可通过环境变量覆盖 model。
    """
    return await _generate_via_openai_image_endpoint(
        "https://ark.cn-beijing.volces.com/api/v3/images/generations",
        backend_config.VOLCENGINE_API_KEY,
        "doubao-seedream-3-0-t2i-250928",
        prompt,
        size,
        n,
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
        data = await asyncio.wait_for(
            call_raw_async(IMAGE_BACKEND, payload),
            timeout=_XMIAOM_IMAGE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        _log.warning("xmiaom image generation timed out after %ss", _XMIAOM_IMAGE_TIMEOUT)
        return []
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
