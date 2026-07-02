"""Browser lifecycle and utility helpers for the probe microservice."""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

from fastapi import HTTPException

from provider_probe import config as probe_config

logger = logging.getLogger("provider_probe.browser")

BROWSER_HOST = probe_config.browser_host()
BROWSER_PORT = probe_config.browser_port()
CHROMIUM_EXECUTABLE = probe_config.chromium_executable()
BROWSER_TOKEN = probe_config.browser_token()

_ALLOWED_SCHEMES = {"http", "https"}
_SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "api-key"}

_browser = None
_playwright = None


def _check_auth(token: str | None) -> None:
    """Require a bearer token when PROBE_BROWSER_TOKEN is configured."""
    expected = probe_config.browser_token()
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


_TEST_DOMAINS = {"example.com", "example.org", "www.example.com", "www.example.org"}


def _is_public_host(host: str) -> bool:
    """Return True if host is a public IP/hostname, False for private/internal."""
    if not host or host in ("localhost", "localhost."):
        return False
    if host.lower() in _TEST_DOMAINS:
        return True
    try:
        addr = ipaddress.ip_address(host)
        return not (addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast:
                return False
        return bool(infos)
    except socket.gaierror:
        return True


def _validate_url(url: str) -> str:
    """Validate a probe URL: public host, http/https only."""
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(status_code=400, detail=f"URL scheme must be http or https: {url}")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail=f"URL has no host: {url}")
    if not _is_public_host(parsed.hostname):
        raise HTTPException(status_code=400, detail=f"URL host is not public: {parsed.hostname}")
    return url


def _sanitize_error(message: str) -> str:
    """Keep operator-visible errors useful without leaking local paths."""
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    first_line = lines[0] if lines else "unknown error"
    first_line = re.sub(
        r"(/root|/home/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+)[^\s'\"<]*",
        "<redacted-path>",
        first_line,
    )
    return first_line[:300]


def _browser_error_detail(exc: Exception, *, phase: str) -> dict[str, object]:
    return {
        "ready": False,
        "service": "probe-browser",
        "phase": phase,
        "error_class": type(exc).__name__,
        "error": _sanitize_error(str(exc)),
    }


def _browser_launch_options() -> dict[str, object]:
    options: dict[str, object] = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    }
    executable = probe_config.chromium_executable()
    if executable:
        options["executable_path"] = executable
    return options


async def _get_browser():
    global _browser, _playwright
    if _browser is None:
        try:
            from playwright.async_api import async_playwright

            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(**_browser_launch_options())
            logger.info("Browser launched")
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail={
                    "ready": False,
                    "service": "probe-browser",
                    "phase": "import",
                    "error_class": "ImportError",
                    "error": "playwright not installed",
                },
            )
    return _browser


async def _close_browser():
    global _browser, _playwright
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
    logger.info("Browser closed")


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove sensitive headers from captured network requests."""
    return {k: "<redacted>" if k.lower() in _SENSITIVE_HEADERS else v for k, v in headers.items()}
