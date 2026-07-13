"""SEC-04 image URL validation for server-side fetches (gallery draw, dlc_api)."""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse, urlunparse

import httpx

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
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast


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


# --------------------------------------------------------------------------- #
#  Pin-IP: resolve-then-connect to defeat DNS rebinding / TOCTOU
# --------------------------------------------------------------------------- #


def validate_and_pin_ip(image_url: str) -> tuple[str, str, str]:
    """Resolve URL host, assert ALL addresses are public, return pin info.

    Returns:
        (url, pinned_ip, original_host)

    Raises:
        ValueError on any validation failure.
    """
    url = image_url.strip()
    if not url:
        raise ValueError("image_url is required")
    if not url.startswith(("https://", "http://")):
        raise ValueError("image_url must be an http(s) URL")

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("image_url host not allowed")

    if _is_private_ip(hostname):
        raise ValueError("image_url hostname is blocked (private/loopback/link-local)")

    try:
        addrs = _resolve_hostname(hostname)
    except OSError as exc:
        raise ValueError(f"image_url host could not be resolved: {hostname}") from exc

    if not addrs:
        raise ValueError(f"image_url host could not be resolved: {hostname}")

    for addr in addrs:
        if _is_private_ip(addr):
            raise ValueError("image_url resolves to a blocked (private) address")

    pinned_ip = addrs[0]
    return url, pinned_ip, hostname


async def fetch_pinned(image_url: str, *, timeout: float = 30.0) -> bytes:
    """Download image_url with pin-IP protection against SSRF/DNS-rebinding.

    Raises:
        ValueError on validation failure.
        httpx.HTTPStatusError on non-2xx response.
    """
    url, pinned_ip, original_host = validate_and_pin_ip(image_url)

    parsed = urlparse(url)
    pinned_netloc = f"{pinned_ip}:{parsed.port}" if parsed.port else pinned_ip
    pinned_url = urlunparse(parsed._replace(netloc=pinned_netloc))

    headers = {"Host": original_host}

    extensions: dict | None = None
    if parsed.scheme == "https":
        extensions = {"sni_hostname": original_host}

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        verify=True,
    ) as client:
        resp = await client.get(
            pinned_url,
            headers=headers,
            extensions=extensions,
        )
        resp.raise_for_status()
        return resp.content
