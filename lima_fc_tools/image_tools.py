"""Image generation tools — DashScope / 通义万相 integration."""

from __future__ import annotations

import os
from typing import Any

from .registry import tool


def _get_api_key() -> str:
    """Return the DashScope API key from environment."""
    return os.environ.get("LIMA_IMAGE_GEN_API_KEY", "")


@tool(
    "generate_image",
    "Generate an image from a text prompt using DashScope (通义万相). "
    "Returns a URL to the generated image.",
    {
        "properties": {
            "prompt": {
                "description": "Text description of the image to generate.",
                "type": "string",
            },
            "style": {
                "default": "<auto>",
                "description": "Image style: '<auto>', 'photography', 'illustration', "
                "'anime', '3d', 'oil_painting', 'watercolor', 'sketch'.",
                "type": "string",
            },
            "size": {
                "default": "1024*1024",
                "description": "Image dimensions: '1024*1024', '720*1280', '1280*720'.",
                "type": "string",
            },
        },
        "required": ["prompt"],
        "type": "object",
    },
)
async def _generate_image(
    prompt: str,
    style: str = "<auto>",
    size: str = "1024*1024",
) -> dict[str, Any]:
    """Generate an image via DashScope API."""
    api_key = _get_api_key()
    if not api_key:
        return {
            "error": "LIMA_IMAGE_GEN_API_KEY environment variable is not set. "
            "Please configure a DashScope API key to use image generation."
        }

    try:
        import httpx

        # DashScope API for 通义万相 image generation
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        payload: dict[str, Any] = {
            "model": "wanx-v1",
            "input": {"prompt": prompt},
            "parameters": {
                "style": style,
                "size": size,
                "n": 1,
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json()

        if resp.status_code != 200:
            return {
                "error": f"API returned HTTP {resp.status_code}",
                "detail": str(data)[:500],
            }

        # Async task — poll for result
        task_id = data.get("output", {}).get("task_id", "")
        if not task_id:
            # Try sync response
            results = data.get("output", {}).get("results", [])
            if results:
                return {
                    "prompt": prompt,
                    "style": style,
                    "size": size,
                    "image_url": results[0].get("url", ""),
                }
            return {"error": "No task_id or results in response", "raw": str(data)[:500]}

        # Poll for async result
        status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        import asyncio

        for _ in range(30):  # Max 30 polls (~30 seconds)
            await asyncio.sleep(1)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    poll_resp = await client.get(status_url, headers={"Authorization": f"Bearer {api_key}"})
                    poll_data = poll_resp.json()
            except asyncio.CancelledError:
                raise
            except Exception as poll_exc:
                continue  # transient network error, keep polling

            task_status = poll_data.get("output", {}).get("task_status", "")
            if task_status == "SUCCEEDED":
                results = poll_data.get("output", {}).get("results", [])
                if results:
                    return {
                        "prompt": prompt,
                        "style": style,
                        "size": size,
                        "image_url": results[0].get("url", ""),
                        "task_id": task_id,
                    }
                return {"error": "Task succeeded but no results", "task_id": task_id}
            elif task_status == "FAILED":
                msg = poll_data.get("output", {}).get("message", "unknown error")
                return {"error": f"Generation failed: {msg}", "task_id": task_id}
            # Still running, continue polling

        return {"error": "Generation timed out after 30 seconds", "task_id": task_id}

    except Exception as exc:
        return {"error": str(exc), "prompt": prompt}
