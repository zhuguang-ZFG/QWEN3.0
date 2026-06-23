"""Browser probe: JS-rendered page extraction via Playwright browser service.

For websites that require JavaScript rendering (most modern AI provider
sites), uses the Playwright browser service to extract API information.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

BROWSER_SERVICE_URL = os.environ.get("PROBE_BROWSER_URL", "http://127.0.0.1:8092")

# Sites that likely contain AI API information but require JS rendering
_JS_HEAVY_SITES = [
    # API aggregators and directories
    "https://openrouter.ai/models?free=true",
    "https://kilo.ai/models",
    "https://github.com/mnfst/awesome-free-llm-apis",
    # Chinese platforms
    "https://api-docs.deepseek.com",
    "https://platform.moonshot.cn/docs",
    "https://open.bigmodel.cn/dev/api",
    # New providers (add as discovered)
]


async def probe_site(
    url: str,
    extract_text: bool = True,
    screenshot: bool = False,
    wait_ms: int = 5000,
) -> dict | None:
    """Use browser service to render a page and extract content."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{BROWSER_SERVICE_URL}/render",
                json={
                    "url": url,
                    "wait_ms": wait_ms,
                    "extract_text": extract_text,
                    "screenshot": screenshot,
                },
            )
            if resp.status_code == 200:
                return resp.json()
            logger.debug("probe_site %s: HTTP %d", url[:60], resp.status_code)
            return None
    except Exception as exc:
        logger.warning("probe_site %s: %s", url[:60], exc)
        return None


async def intercept_network(url: str, wait_ms: int = 8000) -> list[dict]:
    """Navigate to a site and capture API calls made by the page.

    Useful for finding internal API endpoints used by web chat interfaces.
    """
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{BROWSER_SERVICE_URL}/network-intercept",
                json={"url": url, "wait_ms": wait_ms},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("api_calls", [])
            return []
    except Exception as exc:
        logger.warning("intercept_network %s: %s", url[:60], exc)
        return []


async def probe_known_sites() -> list[dict]:
    """Probe all known JS-heavy sites for API information."""
    results: list[dict] = []

    for url in _JS_HEAVY_SITES:
        logger.info("Browser probing: %s", url[:80])
        data = await probe_site(url)
        if data:
            results.append(
                {
                    "url": url,
                    "title": data.get("title", ""),
                    "text_preview": data.get("text", "")[:2000],
                    "network_count": len(data.get("network_requests", [])),
                }
            )

    return results


async def reverse_web_chat(url: str) -> dict:
    """Attempt to reverse-engineer a web-based AI chat interface.

    Navigates to the chat page, intercepts network requests, and tries
    to identify the internal API endpoint and authentication mechanism.

    Args:
        url: The web chat URL (e.g., https://chat.example.com)

    Returns:
        Dict with discovered API details or empty on failure.
    """
    logger.info("Reverse-engineering web chat: %s", url)

    # Step 1: Intercept network requests
    api_calls = await intercept_network(url, wait_ms=10000)
    if not api_calls:
        logger.debug("No API calls intercepted from %s", url)
        return {}

    # Step 2: Analyze intercepted calls for chat API patterns
    chat_endpoints = []
    for call in api_calls:
        call_url = call.get("url", "")
        if any(kw in call_url.lower() for kw in ("chat", "completion", "message", "conversation", "stream")):
            chat_endpoints.append(
                {
                    "url": call_url,
                    "method": call.get("method", "POST"),
                    "headers": call.get("headers", {}),
                }
            )

    # Step 3: Try to identify auth mechanism
    auth_info = {"type": "unknown"}
    for call in api_calls:
        headers = call.get("headers", {})
        if "authorization" in headers:
            auth_val = headers["authorization"]
            if auth_val.startswith("Bearer "):
                auth_info = {"type": "bearer", "prefix": "Bearer", "example": auth_val[:30] + "..."}
            elif auth_val.startswith("Basic "):
                auth_info = {"type": "basic"}
        elif "x-api-key" in headers:
            auth_info = {"type": "x-api-key", "example": headers["x-api-key"][:20] + "..."}

    return {
        "url": url,
        "api_endpoints": chat_endpoints,
        "auth": auth_info,
        "total_api_calls": len(api_calls),
    }
