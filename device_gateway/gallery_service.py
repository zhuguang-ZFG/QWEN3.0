"""Gallery list enrichment, stable proxy URLs, and cached image proxy bytes."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

from fastapi import Request

from config import settings
from device_gateway import gallery_store
from device_gateway.gallery_storage import GalleryStorageBackend

_log = logging.getLogger(__name__)

THUMB_CACHE_MAX_AGE_SECONDS = 3600
GALLERY_PRELOAD_DEFAULT_COUNT = 6
GALLERY_PROXY_RATE_LIMIT_PER_MIN = 60
GALLERY_FETCH_TOKEN_TTL_SECONDS = 600
GALLERY_THUMB_TOKEN_TTL_SECONDS = THUMB_CACHE_MAX_AGE_SECONDS
_PROXY_CACHE_TTL_SECONDS = 3600
_PROXY_CACHE_MAX_ENTRIES = 256

_proxy_cache: dict[str, tuple[bytes, str, float]] = {}


def clear_proxy_cache_for_tests() -> None:
    """Reset the in-process gallery proxy cache (tests only)."""
    _proxy_cache.clear()


def stable_thumb_path(image_id: str) -> str:
    return f"/device/v1/app/gallery/{image_id}/thumb"


def stable_file_path(image_id: str) -> str:
    return f"/device/v1/app/gallery/{image_id}/file"


def _absolute_url(request: Request, path: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}{path}"


def stable_thumb_url(request: Request, image_id: str) -> str:
    return _absolute_url(request, stable_thumb_path(image_id))


def stable_file_url(request: Request, image_id: str) -> str:
    return _absolute_url(request, stable_file_path(image_id))


def _gallery_signing_secret() -> str | None:
    secret = settings.SECURITY.jwt_secret
    return secret or None


def issue_gallery_fetch_token(
    account_id: str, image_id: str, *, ttl_seconds: int = GALLERY_FETCH_TOKEN_TTL_SECONDS
) -> str | None:
    """Issue a short-lived HMAC token for server-side gallery file fetches."""
    secret = _gallery_signing_secret()
    if not secret:
        return None
    expires_at = int(time.time()) + max(30, ttl_seconds)
    payload = f"{expires_at}:{account_id}:{image_id}"
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{digest}"


def parse_gallery_fetch_token(token: str) -> tuple[str, str] | None:
    """Return (account_id, image_id) when *token* is valid; otherwise None."""
    secret = _gallery_signing_secret()
    if not secret or not token:
        return None
    parts = token.split(":")
    if len(parts) != 4:
        return None
    expires_raw, account_id, image_id, digest = parts
    try:
        expires_at = int(expires_raw)
    except ValueError:
        return None
    if expires_at < int(time.time()):
        return None
    payload = f"{expires_at}:{account_id}:{image_id}"
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, digest):
        return None
    return account_id, image_id


def stable_file_download_url(request: Request, account_id: str, image_id: str) -> str:
    """Stable /file URL with a short-lived fetch token for server-side draw tasks."""
    base_url = stable_file_url(request, image_id)
    fetch_token = issue_gallery_fetch_token(account_id, image_id)
    if not fetch_token:
        return base_url
    query = urlencode({"fetch_token": fetch_token})
    return f"{base_url}?{query}"


def issue_gallery_thumb_token(account_id: str, image_id: str) -> str | None:
    """Issue a short-lived HMAC token for mini-program thumb URLs (no JWT in query)."""
    return issue_gallery_fetch_token(
        account_id,
        image_id,
        ttl_seconds=GALLERY_THUMB_TOKEN_TTL_SECONDS,
    )


def internal_gallery_file_url(account_id: str, image_id: str) -> str | None:
    """Build a server-side gallery file URL for draw tasks (not for client persistence)."""
    from config.deploy_config import VERIFY_HOST

    host = (VERIFY_HOST or "").strip()
    if not host:
        return None
    fetch_token = issue_gallery_fetch_token(account_id, image_id)
    if not fetch_token:
        return None
    query = urlencode({"fetch_token": fetch_token})
    return f"https://{host}{stable_file_path(image_id)}?{query}"


def with_stable_urls(image: dict[str, Any], request: Request, account_id: str) -> dict[str, Any]:
    """Return a copy with stable thumb/file proxy URLs (no Telegram URLs)."""
    image_id = str(image["id"])
    enriched = dict(image)
    enriched["thumbUrl"] = stable_thumb_url(request, image_id)
    enriched["thumbPath"] = stable_thumb_path(image_id)
    thumb_token = issue_gallery_thumb_token(account_id, image_id)
    if thumb_token:
        enriched["thumbToken"] = thumb_token
    enriched["fileUrl"] = stable_file_url(request, image_id)
    enriched["filePath"] = stable_file_path(image_id)
    return enriched


async def list_images_for_app(
    account_id: str,
    *,
    request: Request,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """List gallery images with stable proxy URLs (no Telegram refresh on list)."""
    images = gallery_store.list_images(account_id, limit=limit, offset=offset)
    return [with_stable_urls(image, request, account_id) for image in images]


async def load_image_bytes(image: dict[str, Any], backend: GalleryStorageBackend) -> tuple[bytes, str]:
    """Download full image bytes from the configured storage backend."""
    file_id = str(image.get("fileId") or image.get("file_id") or "")
    url = await backend.get_file_url(file_id)
    content = await backend.download_file(url)
    mime_type = str(image.get("mimeType") or image.get("mime_type") or "image/jpeg")
    return content, mime_type


async def load_thumb_bytes(image: dict[str, Any], backend: GalleryStorageBackend) -> tuple[bytes, str]:
    """Download thumbnail bytes when available; fall back to full image."""
    thumb_url = str(image.get("thumbUrl") or image.get("thumb_url") or "").strip()
    if thumb_url:
        content = await backend.download_file(thumb_url)
        return content, "image/jpeg"
    return await load_image_bytes(image, backend)


async def get_cached_image_bytes(
    account_id: str,
    image_id: str,
    image: dict[str, Any],
    backend: GalleryStorageBackend,
    *,
    for_file: bool = True,
) -> tuple[bytes, str]:
    """Return proxied image bytes, with a small in-process TTL cache."""
    cache_key = f"{account_id}:{image_id}:{'file' if for_file else 'thumb'}"
    now = time.time()
    cached = _proxy_cache.get(cache_key)
    if cached and cached[2] > now:
        return cached[0], cached[1]

    if for_file:
        content, mime_type = await load_image_bytes(image, backend)
    else:
        content, mime_type = await load_thumb_bytes(image, backend)
    _proxy_cache[cache_key] = (content, mime_type, now + _PROXY_CACHE_TTL_SECONDS)
    if len(_proxy_cache) > _PROXY_CACHE_MAX_ENTRIES:
        oldest_key = min(_proxy_cache, key=lambda key: _proxy_cache[key][2])
        _proxy_cache.pop(oldest_key, None)
    return content, mime_type


def proxy_cache_headers(*, jwt_query_auth: bool, for_file: bool = False) -> dict[str, str]:
    """Cache policy for gallery proxy responses."""
    if jwt_query_auth or for_file:
        return {"Cache-Control": "no-store, private"}
    return {"Cache-Control": f"private, max-age={THUMB_CACHE_MAX_AGE_SECONDS}"}
