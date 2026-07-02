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
                    result["auth_type"] = "bearer" if "Authorization" in header_name else "api-key"
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
        except Exception as exc:
            logging.debug("auth probe failed for %s: %s", url, exc)
            continue

    # If we got 401/403 with test keys, auth is required but mechanism unclear
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code in (401, 403):
                result["requires_auth"] = True
                result["evidence"] = f"HTTP {resp.status_code} without auth"
    except Exception as exc:
        # Auth probe failures are expected for unreachable or non-compliant endpoints.
        logger.warning("auth detection HTTP probe failed for %s: %s", url, exc)

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
            resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
            result["status"] = resp.status_code
            if resp.status_code == 200:
                result["requires_auth"] = False
                result["evidence"] = "200 OK without auth"
                return result
    except Exception as exc:
        # Chat auth probe failure is expected when the endpoint rejects unauthenticated probes.
        logger.warning("chat auth probe failed for %s: %s", url, exc)

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
        except Exception as exc:
            # Auth header probe failure is expected for invalid or unsupported auth schemes.
            logger.warning("auth header probe failed for %s with %s: %s", url, header_name, exc)

    return result
