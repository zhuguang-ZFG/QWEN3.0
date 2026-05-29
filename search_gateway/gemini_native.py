"""Gemini Native Adapter v0.1 — direct generateContent API for advanced features.

Uses GOOGLE_AI_KEY from environment. Enables Gemini features not available
through the OpenAI-compatible endpoint:
  - generateContent with systemInstruction
  - countTokens
  - Google Search grounding (grounding via googleSearch tool)
  - URL context (pass URLs as parts for inline retrieval)

Privacy rule: private code is never sent to Google. Only public doc retrieval.
Controlled by LIMA_GOOGLE_NATIVE=1 (default-off).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

_log = logging.getLogger(__name__)

_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_MODEL = "gemini-2.5-flash"
_TIMEOUT = 30
_ENABLED = os.environ.get("LIMA_GOOGLE_NATIVE", "0").strip().lower() in {
    "1", "true", "yes",
}
_API_KEY = os.environ.get("GOOGLE_AI_KEY", "")
_GFW_PROXY = os.environ.get("GFW_PROXY", "")


def _api_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make an authenticated Gemini API request."""
    if not _API_KEY:
        return {"ok": False, "error": "GOOGLE_AI_KEY not configured"}
    if not _ENABLED:
        return {"ok": False, "error": "LIMA_GOOGLE_NATIVE=0"}

    url = f"{_API_BASE}{path}?key={_API_KEY}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")

    # GFW proxy support
    if _GFW_PROXY:
        proxy = urllib.request.ProxyHandler({"https": _GFW_PROXY})
        opener = urllib.request.build_opener(proxy)
    else:
        opener = urllib.request.build_opener()

    try:
        with opener.open(req, timeout=_TIMEOUT) as resp:
            return {"ok": True, "data": json.loads(resp.read())}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        _log.warning("Gemini API %s: %s %s", path, exc.code, detail)
        return {"ok": False, "error": f"Gemini {exc.code}", "detail": detail[:300]}
    except Exception as exc:
        _log.warning("Gemini API %s: %s", path, exc)
        return {"ok": False, "error": str(exc)[:300]}


def generate_content(
    prompt: str,
    *,
    model: str = _DEFAULT_MODEL,
    system_instruction: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    tools: list[dict] | None = None,
    grounding: bool = False,
) -> dict:
    """Call Gemini generateContent with optional Google Search grounding.

    Args:
        prompt: User text to send to Gemini.
        model: Gemini model ID (e.g. gemini-2.5-flash).
        system_instruction: Optional system prompt.
        temperature: 0.0-1.0.
        max_tokens: Max output tokens.
        tools: Optional tool definitions (e.g. googleSearch).
        grounding: If True, enable Google Search grounding.

    Privacy: caller must ensure private code is NOT sent here.
    """
    parts: list[dict] = [{"text": prompt[:32000]}]

    body: dict = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction[:8000]}]}

    if grounding:
        body["tools"] = [{"googleSearch": {}}]

    if tools:
        body.setdefault("tools", []).extend(tools)

    result = _api_request(
        "POST", f"/models/{model}:generateContent", body,
    )
    if result.get("ok") and result.get("data"):
        data = result["data"]
        candidates = data.get("candidates", [])
        text = ""
        grounding_metadata = None
        for c in candidates:
            content = c.get("content", {})
            for p in content.get("parts", []):
                if "text" in p:
                    text += p["text"]
        # Extract grounding sources if available
        if candidates:
            gm = candidates[0].get("groundingMetadata", {})
            if gm:
                grounding_metadata = {
                    "sources": [
                        {"uri": s.get("uri", ""), "title": s.get("title", "")}
                        for chunk in gm.get("groundingChunks", [])
                        for s in [chunk.get("web", {})]
                        if s
                    ]
                }
        return {
            "ok": True,
            "text": text,
            "model": model,
            "finish_reason": candidates[0].get("finishReason", "") if candidates else "",
            "token_count": data.get("usageMetadata", {}).get("totalTokenCount", 0),
            "grounding": grounding_metadata,
        }
    return result


def count_tokens(
    text: str,
    *,
    model: str = _DEFAULT_MODEL,
    system_instruction: str = "",
) -> dict:
    """Count tokens for a text using Gemini's countTokens API."""
    parts: list[dict] = [{"text": text[:32000]}]
    body: dict = {"contents": [{"parts": parts}]}
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction[:8000]}]}

    result = _api_request(
        "POST", f"/models/{model}:countTokens", body,
    )
    if result.get("ok") and result.get("data"):
        return {"ok": True, "total_tokens": result["data"].get("totalTokens", 0)}
    return result


def generate_with_url(
    prompt: str,
    urls: list[str],
    *,
    model: str = _DEFAULT_MODEL,
) -> dict:
    """Ask Gemini about web content at given URLs (inline URL context).

    Uses Gemini's native fileData/URL part type for inline retrieval.
    Works for public URLs only (Gemini fetches them server-side).
    """
    parts: list[dict] = []
    for url in urls[:5]:
        parts.append({"fileData": {"fileUri": url}})
    parts.append({"text": prompt[:16000]})

    body: dict = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 4096,
        },
    }

    result = _api_request(
        "POST", f"/models/{model}:generateContent", body,
    )
    if result.get("ok") and result.get("data"):
        data = result["data"]
        text = ""
        for c in data.get("candidates", []):
            for p in c.get("content", {}).get("parts", []):
                if "text" in p:
                    text += p["text"]
        return {"ok": True, "text": text, "model": model}
    return result
