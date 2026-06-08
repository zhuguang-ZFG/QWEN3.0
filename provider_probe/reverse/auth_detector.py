"""Auth detector: identify authentication mechanism of API providers."""

import logging

import httpx

logger = logging.getLogger(__name__)

AUTH_HEADERS = [
    ("Authorization", "Bearer test"),
    ("x-api-key", "test"),
    ("api-key", "test"),
]


async def detect_auth(base_url: str) -> dict:
    """Detect authentication requirements for a provider API.

    Returns dict with: requires_auth, auth_type, auth_header_name
    """
    result = {
        "requires_auth": False,
        "auth_type": "none",
        "auth_header_name": "",
        "evidence": "",
    }

    # Try unauthenticated access first
    url = base_url.rstrip("/") + "/v1/models"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                result["requires_auth"] = False
                result["auth_type"] = "none"
                result["evidence"] = "200 OK without auth"
                return result
    except Exception:
        return result

    # Try common auth headers and see which one changes the response
    for header_name, header_value in AUTH_HEADERS:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    url,
                    headers={header_name: header_value},
                    follow_redirects=True,
                )
                if resp.status_code == 200:
                    result["requires_auth"] = True
                    result["auth_header_name"] = header_name
                    result["auth_type"] = (
                        "bearer" if "Authorization" in header_name else "api-key"
                    )
                    result["evidence"] = f"200 OK with {header_name}"
                    return result
                elif resp.status_code in (401, 403):
                    www_auth = resp.headers.get("www-authenticate", "").lower()
                    if "bearer" in www_auth:
                        result["requires_auth"] = True
                        result["auth_type"] = "bearer"
                        result["auth_header_name"] = "Authorization"
                        result["evidence"] = f"401 with www-authenticate: {www_auth[:80]}"
                        return result
        except Exception:
            continue

    # If we got 401/403 with test keys, auth is required but mechanism unclear
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code in (401, 403):
                result["requires_auth"] = True
                result["evidence"] = f"HTTP {resp.status_code} without auth"
    except Exception:
        logger.debug("auth detection HTTP probe failed", exc_info=True)

    return result


async def probe_chat_auth(base_url: str) -> dict:
    """Probe whether chat completions endpoint requires auth."""
    url = base_url.rstrip("/") + "/v1/chat/completions"
    body = {
        "model": "test",
        "messages": [{"role": "user", "content": "hi"}],
    }

    result = {"endpoint": url, "status": 0, "requires_auth": True}

    # Try without auth
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url, json=body, headers={"Content-Type": "application/json"}
            )
            result["status"] = resp.status_code
            if resp.status_code == 200:
                result["requires_auth"] = False
                result["evidence"] = "200 OK without auth"
                return result
    except Exception:
        logger.debug("chat auth probe failed", exc_info=True)

    # Try with auth headers
    for header_name, header_value in AUTH_HEADERS:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    json=body,
                    headers={
                        "Content-Type": "application/json",
                        header_name: header_value,
                    },
                )
                if resp.status_code == 200:
                    result["status"] = 200
                    result["requires_auth"] = True
                    result["auth_header"] = header_name
                    return result
        except Exception:
            logger.debug("auth header probe failed", exc_info=True)

    return result
