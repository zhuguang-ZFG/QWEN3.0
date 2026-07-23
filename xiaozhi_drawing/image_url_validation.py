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


def _require_allowed_host(hostname: str, allowed_hosts: frozenset[str] | None) -> frozenset[str]:
    """Return the effective allowlist and raise if hostname is not in it."""
    if allowed_hosts is None:
        allowed_hosts = allowed_image_hosts()
    if allowed_hosts and hostname not in allowed_hosts:
        raise ValueError(f"image_url host not allowed: {hostname}")
    return allowed_hosts


def validate_and_pin_ip(
    image_url: str,
    *,
    allowed_hosts: frozenset[str] | None = None,
) -> tuple[str, str, str]:
    """Resolve URL host, assert ALL addresses are public and host is allowlisted, return pin info.

    Args:
        image_url: URL to validate and pin.
        allowed_hosts: Explicit allowlist of hostnames. If ``None``, the
            default ``allowed_image_hosts()`` (SEC-04) is used. Pass an empty
            ``frozenset()`` to skip host-allowlist checks while still blocking
            private/loopback addresses (e.g., for URLs returned by a trusted
            internal service such as DashScope).

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

    _require_allowed_host(hostname, allowed_hosts)

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


async def fetch_pinned(
    image_url: str,
    *,
    timeout: float = 30.0,
    allowed_hosts: frozenset[str] | None = None,
) -> bytes:
    """Download image_url with pin-IP protection against SSRF/DNS-rebinding.

    Args:
        image_url: URL to download.
        timeout: Request timeout in seconds.
        allowed_hosts: Explicit host allowlist. ``None`` applies the default
            SEC-04 allowlist. Pass an empty ``frozenset()`` to allow any public
            host (use only for URLs from a trusted internal service).

    Raises:
        ValueError on validation failure.
        httpx.HTTPStatusError on non-2xx response.
    """
    url, pinned_ip, original_host = validate_and_pin_ip(image_url, allowed_hosts=allowed_hosts)

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
