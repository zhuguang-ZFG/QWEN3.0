"""Pollinations.ai image URL builder with optional Chinese prompt translation."""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse

import httpx

_log = logging.getLogger(__name__)

_POLLINATIONS_BASE_URL = "https://image.pollinations.ai"
_PROMPT_TRANSLATE_ENABLED = os.environ.get("LIMA_IMAGE_PROMPT_TRANSLATE_ZH", "1") == "1"
_PROMPT_TRANSLATE_TIMEOUT = int(os.environ.get("LIMA_IMAGE_PROMPT_TRANSLATE_TIMEOUT_SECONDS", "5"))


def build_pollinations_url(prompt: str, size: str = "1024x1024", options: dict | None = None) -> str:
    """Build Pollinations.ai image URL from prompt, size and extra options."""
    options = options or {}
    parts = size.split("x")
    width = int(parts[0]) if len(parts) == 2 else 1024
    height = int(parts[1]) if len(parts) == 2 else 1024

    query: dict[str, str] = {
        "width": str(width),
        "height": str(height),
        "nologo": "true" if options.get("nologo", True) else "false",
    }

    seed = options.get("seed")
    if seed is not None:
        query["seed"] = str(seed)

    model = options.get("model")
    if model and model != "lima-image":
        query["model"] = model

    if options.get("private"):
        query["private"] = "true"
    if options.get("enhance"):
        query["enhance"] = "true"
    if options.get("safe"):
        query["safe"] = "true"

    negative_prompt = options.get("negative_prompt")
    if negative_prompt:
        query["negative"] = negative_prompt

    query_string = urllib.parse.urlencode(query, quote_via=urllib.parse.quote)
    encoded_prompt = urllib.parse.quote(prompt)
    return f"{_POLLINATIONS_BASE_URL}/prompt/{encoded_prompt}?{query_string}"


def build_variant(options: dict) -> str:
    """Return a deterministic cache-key fragment for Pollinations options."""
    return json.dumps(options, sort_keys=True, ensure_ascii=False)


async def _maybe_translate_chinese_prompt(prompt: str) -> str:
    """Translate Chinese prompts to English using Pollinations free text API."""
    if not _PROMPT_TRANSLATE_ENABLED or not re.search(r"[\u4e00-\u9fff]", prompt):
        return prompt

    translate_prompt = (
        "Translate this Chinese image prompt into a concise English prompt "
        f"for image generation, keep the meaning and style: {prompt}"
    )
    encoded = urllib.parse.quote(translate_prompt)
    url = f"https://text.pollinations.ai/{encoded}?model=openai&seed=42"

    try:
        async with httpx.AsyncClient(timeout=_PROMPT_TRANSLATE_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            translated = response.text.strip()
            if translated:
                _log.info("translated zh prompt: %s -> %s", prompt[:40], translated[:80])
                return translated
    except Exception as exc:
        _log.warning("pollinations prompt translation failed: %s", str(exc)[:200])

    return prompt


async def generate_pollinations_urls(prompt: str, size: str, n: int, options: dict | None = None) -> list[dict]:
    """Return n Pollinations image URL objects."""
    translated_prompt = await _maybe_translate_chinese_prompt(prompt)
    url = build_pollinations_url(translated_prompt, size, options)
    return [{"url": url} for _ in range(n)]
