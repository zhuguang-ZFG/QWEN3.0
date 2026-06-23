"""Healthchecks.io dead-man ping helpers (INF-B).

Default off via LIMA_HEALTHCHECK_ENABLED=0 until VPS/Windows smoke evidence exists.
"""

from __future__ import annotations

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_HEALTH_FAIL = 1
EXIT_PING_FAIL = 2
EXIT_SKIP = 0
EXIT_CONFIG = 3

_DEFAULT_TIMEOUT = 10.0
_HEALTH_TIMEOUT = 5.0


def is_healthcheck_enabled() -> bool:
    return settings.FLAGS.healthcheck_enabled


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def ping_healthcheck(
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    client: httpx.Client | None = None,
) -> tuple[bool, str]:
    """Ping a Healthchecks.io URL; returns (ok, detail)."""
    ping_url = _normalize_url(url)
    if not ping_url:
        return False, "empty ping url"

    owns = client is None
    if client is None:
        client = httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        response = client.get(ping_url)
        detail = f"ping status={response.status_code}"
        if response.status_code >= 400:
            detail = f"{detail} body={response.text[:120]!r}"
        return response.status_code < 400, detail
    except httpx.HTTPError as exc:
        return False, f"ping error: {type(exc).__name__}: {exc}"
    finally:
        if owns:
            client.close()


def verify_health_endpoint(
    health_url: str,
    *,
    timeout: float = _HEALTH_TIMEOUT,
    client: httpx.Client | None = None,
) -> tuple[bool, str]:
    """Verify a local /health endpoint before dead-man ping."""
    url = _normalize_url(health_url)
    if not url:
        return False, "empty health url"

    owns = client is None
    if client is None:
        client = httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        response = client.get(url)
        detail = f"health status={response.status_code}"
        if response.status_code >= 400:
            detail = f"{detail} body={response.text[:120]!r}"
        return response.status_code < 400, detail
    except httpx.HTTPError as exc:
        return False, f"health error: {type(exc).__name__}: {exc}"
    finally:
        if owns:
            client.close()


def resolve_ping_url(
    ping_url: str = "",
    *,
    env_key: str = "",
) -> str:
    if ping_url.strip():
        return ping_url.strip()
    if env_key:
        return settings.get_env(env_key, "").strip()
    return ""


def check_then_ping(
    *,
    health_url: str | None = None,
    ping_url: str = "",
    env_key: str = "",
    enabled: bool | None = None,
    client: httpx.Client | None = None,
) -> int:
    """Optional health pre-check, then Healthchecks ping.

    Returns EXIT_OK (0) on success or skip when disabled.
    """
    if enabled is None:
        enabled = is_healthcheck_enabled()
    if not enabled:
        logger.debug("healthcheck ping skipped: LIMA_HEALTHCHECK_ENABLED=0")
        return EXIT_SKIP

    resolved_ping = resolve_ping_url(ping_url, env_key=env_key)
    if not resolved_ping:
        logger.warning("healthcheck ping skipped: no ping url configured")
        return EXIT_CONFIG

    owns = client is None
    if client is None:
        client = httpx.Client(timeout=_DEFAULT_TIMEOUT, follow_redirects=True)
    try:
        if health_url:
            ok, detail = verify_health_endpoint(health_url, client=client)
            if not ok:
                logger.warning("healthcheck pre-check failed: %s", detail)
                return EXIT_HEALTH_FAIL

        ok, detail = ping_healthcheck(resolved_ping, client=client)
        if not ok:
            logger.warning("healthcheck ping failed: %s", detail)
            return EXIT_PING_FAIL

        logger.info("healthcheck ping ok: %s", detail)
        return EXIT_OK
    finally:
        if owns:
            client.close()


def ping_from_env(
    env_key: str,
    *,
    health_url: str | None = None,
    enabled: bool | None = None,
    client: httpx.Client | None = None,
) -> int:
    return check_then_ping(
        health_url=health_url,
        env_key=env_key,
        enabled=enabled,
        client=client,
    )
