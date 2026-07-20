"""SEC-04 image URL validation for server-side fetches (gallery draw, dlc_api)."""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from urllib.parse import urlparse

from config.deploy_config import VERIFY_HOST

_BASE_ALLOWED_IMAGE_HOSTS = frozenset({"api.telegram.org"})


def allowed_image_hosts() -> frozenset[str]:
    """Hosts permitted for server-side image download."""
    hosts = set(_BASE_ALLOWED_IMAGE_HOSTS)
    if VERIFY_HOST:
        hosts.add(VERIFY_HOST.lower())
    extra = os.environ.get("LIMA_ALLOWED_IMAGE_HOSTS", "")
    for item in extra.split(","):
        host = item.strip().lower()
        if host:
            hosts.add(host)
    return frozenset(hosts)


def _is_private_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def _resolve_hostname(hostname: str) -> list[str]:
    return [str(info[4][0]) for info in socket.getaddrinfo(hostname, None)]


def validate_image_url(image_url: str) -> tuple[str | None, str | None]:
    """Return (image_url, error_msg). Exactly one is non-None."""
    url = image_url.strip()
    if not url:
        return None, "image_url is required"
    if not url.startswith(("https://", "http://")):
        return None, "image_url must be an http(s) URL"

    hostname = (urlparse(url).hostname or "").lower()
    if not hostname:
        return None, "image_url host not allowed"

    if _is_private_ip(hostname):
        return None, "image_url hostname is blocked (private/loopback/link-local)"

    if hostname not in allowed_image_hosts():
        return None, f"image_url host not allowed: {hostname}"

    try:
        addrs = _resolve_hostname(hostname)
    except OSError:
        return None, f"image_url host could not be resolved: {hostname}"
    if any(_is_private_ip(addr) for addr in addrs):
        return None, "image_url resolves to a blocked (private) address"

    return url, None


async def validate_image_url_async(image_url: str) -> tuple[str | None, str | None]:
    """GW-WD: DNS resolution (getaddrinfo) is blocking — run validation off-loop."""
    return await asyncio.to_thread(validate_image_url, image_url)
