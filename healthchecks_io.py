"""Healthchecks.io check provisioning helpers (INF-B)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://healthchecks.io/api/v3"
_DEFAULT_TIMEOUT = 600
_DEFAULT_GRACE = 300


def slug_ping_url(ping_key: str, slug: str) -> str:
    key = ping_key.strip().strip("/")
    name = slug.strip().strip("/")
    return f"https://hc-ping.com/{key}/{name}"


def provision_slug_check(
    ping_key: str,
    slug: str,
    *,
    create: bool = True,
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> tuple[bool, str]:
    """Ping slug URL; with create=1 auto-provisions the check on first success."""
    url = slug_ping_url(ping_key, slug)
    if create:
        url = f"{url}?create=1"
    owns = client is None
    if client is None:
        client = httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        response = client.get(url)
        detail = f"slug ping status={response.status_code}"
        if response.status_code >= 400:
            detail = f"{detail} body={response.text[:120]!r}"
        return response.status_code < 400, detail
    except httpx.HTTPError as exc:
        return False, f"slug ping error: {type(exc).__name__}: {exc}"
    finally:
        if owns:
            client.close()


def _extract_ping_url(payload: dict[str, Any]) -> str:
    for key in ("ping_url", "update_url"):
        raw = str(payload.get(key) or "").strip()
        if raw.startswith("https://hc-ping.com/"):
            return raw.rstrip("/")
    ping_url = str(payload.get("ping_url") or "").strip()
    return ping_url.rstrip("/")


def find_check_by_name(
    api_key: str,
    name: str,
    *,
    timeout: float = 20.0,
    client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    owns = client is None
    if client is None:
        client = httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        response = client.get(
            f"{_API_BASE}/checks/",
            headers={"X-Api-Key": api_key.strip()},
        )
        if response.status_code >= 400:
            logger.warning("healthchecks list failed status=%s", response.status_code)
            return None
        for check in response.json().get("checks") or []:
            if isinstance(check, dict) and str(check.get("name") or "") == name:
                return check
        return None
    except httpx.HTTPError:
        logger.warning("healthchecks list error", exc_info=True)
        return None
    finally:
        if owns:
            client.close()


def ensure_check_via_api(
    api_key: str,
    name: str,
    *,
    timeout_sec: int = _DEFAULT_TIMEOUT,
    grace_sec: int = _DEFAULT_GRACE,
    client: httpx.Client | None = None,
) -> tuple[str | None, str]:
    """Create or reuse a simple check; return (ping_url, detail)."""
    key = api_key.strip()
    if not key:
        return None, "empty api key"

    owns = client is None
    if client is None:
        client = httpx.Client(timeout=20.0, follow_redirects=True)
    try:
        existing = find_check_by_name(key, name, client=client)
        if existing:
            ping = _extract_ping_url(existing)
            if ping:
                return ping, f"reused check name={name}"

        response = client.post(
            f"{_API_BASE}/checks/",
            headers={"X-Api-Key": key},
            json={
                "name": name,
                "timeout": timeout_sec,
                "grace": grace_sec,
            },
        )
        if response.status_code >= 400:
            return None, f"create failed status={response.status_code} body={response.text[:160]!r}"
        payload = response.json()
        ping = _extract_ping_url(payload)
        if not ping:
            return None, "create ok but ping_url missing"
        return ping, f"created check name={name}"
    except httpx.HTTPError as exc:
        return None, f"api error: {type(exc).__name__}: {exc}"
    finally:
        if owns:
            client.close()


def resolve_vps_router_ping_url(
    *,
    ping_url: str = "",
    api_key: str = "",
    ping_key: str = "",
    slug: str = "lima-vps-router",
) -> tuple[str | None, str]:
    """Resolve ping URL from explicit value, API key, or slug auto-provision."""
    direct = ping_url.strip()
    if direct:
        return direct.rstrip("/"), "explicit ping url"

    if api_key.strip():
        url, detail = ensure_check_via_api(api_key.strip(), slug.replace("-", " ").title())
        if url:
            return url, detail
        return None, detail

    if ping_key.strip():
        ok, detail = provision_slug_check(ping_key.strip(), slug, create=True)
        if ok:
            return slug_ping_url(ping_key.strip(), slug), f"slug provision ok ({detail})"
        return None, detail

    return None, "no ping url, api key, or ping key configured"
