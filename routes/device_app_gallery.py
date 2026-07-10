"""Device app gallery routes backed by Telegram Bot storage.

Images are uploaded to Telegram; LiMa only stores file IDs and metadata.
If TELEGRAM_BOT_TOKEN is not configured, gallery endpoints return 503.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from device_gateway import gallery_store
from device_gateway.gallery_service import (
    GALLERY_PROXY_RATE_LIMIT_PER_MIN,
    get_cached_image_bytes,
    list_images_for_app,
    proxy_cache_headers,
    stable_file_download_url,
    parse_gallery_fetch_token,
    with_stable_urls,
)
from device_gateway.gallery_storage import get_gallery_backend
from device_logic.auth import authorize
from device_logic.http import err
from integrations.telegram_bot.client import TelegramFileTooLargeError, TelegramNotConfiguredError
from routes.rate_limit_helper import check_key_limit

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/device/v1/app", tags=["device-app-gallery"])

_ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _account_id(account: dict[str, Any] | JSONResponse) -> str | JSONResponse:
    if isinstance(account, JSONResponse):
        return account
    return str(account.get("id", ""))


def _authorize_gallery(
    authorization: str,
    access_token: str = "",
    *,
    image_id: str = "",
    fetch_token: str = "",
    thumb_token: str = "",
) -> tuple[dict[str, Any] | JSONResponse, bool]:
    """Authorize via Bearer header, access_token query, fetch_token, or thumb_token."""
    hmac_token = fetch_token.strip() or thumb_token.strip()
    if hmac_token and image_id:
        parsed = parse_gallery_fetch_token(hmac_token)
        if parsed and parsed[1] == image_id:
            return {"id": parsed[0]}, False

    header_auth = authorization.strip()
    used_query_token = bool(access_token.strip() and not header_auth)
    if used_query_token:
        header_auth = f"Bearer {access_token.strip()}"
        _log.debug("gallery proxy authorized via access_token query param")
    return authorize(header_auth), used_query_token


def _validate_upload(file: UploadFile, content: bytes) -> JSONResponse | None:
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        return err(400, f"unsupported content type: {file.content_type}", 400)
    if len(content) > _MAX_UPLOAD_BYTES:
        return err(413, f"file size exceeds {_MAX_UPLOAD_BYTES / 1024 / 1024}MB", 413)
    return None


def _gallery_not_configured_response(exc: TelegramNotConfiguredError) -> JSONResponse:
    _log.warning("gallery request rejected: %s", exc)
    return err(503, "gallery storage is not configured", 503)


async def _serve_gallery_proxy(
    image_id: str,
    authorization: str,
    access_token: str,
    fetch_token: str = "",
    *,
    thumb_token: str = "",
    for_file: bool,
) -> Response | JSONResponse:
    account, used_jwt_query = _authorize_gallery(
        authorization,
        access_token,
        image_id=image_id,
        fetch_token=fetch_token,
        thumb_token=thumb_token,
    )
    account_id = _account_id(account)
    if isinstance(account_id, JSONResponse):
        return account_id

    image = gallery_store.get_image(image_id, account_id)
    if image is None:
        return err(404, "image not found", 404)

    limited = check_key_limit(
        f"gallery_proxy:{account_id}",
        GALLERY_PROXY_RATE_LIMIT_PER_MIN,
        window=60.0,
    )
    if limited is not None:
        return limited

    try:
        backend = get_gallery_backend()
        content, mime_type = await get_cached_image_bytes(account_id, image_id, image, backend, for_file=for_file)
    except TelegramNotConfiguredError as exc:
        return _gallery_not_configured_response(exc)
    except Exception as exc:
        label = "file" if for_file else "thumb"
        _log.exception("failed to proxy gallery %s for %s", label, image_id)
        return err(500, f"gallery {label} proxy failed: {exc}", 500)

    return Response(
        content=content,
        media_type=mime_type,
        headers=proxy_cache_headers(jwt_query_auth=used_jwt_query, for_file=for_file),
    )


@router.post("/gallery")
async def upload_gallery_image(
    request: Request,
    file: UploadFile,
    authorization: str = Header(default=""),
) -> JSONResponse:
    """Upload an image to Telegram gallery and return its metadata."""
    account = authorize(authorization)
    account_id = _account_id(account)
    if isinstance(account_id, JSONResponse):
        return account_id

    try:
        backend = get_gallery_backend()
    except TelegramNotConfiguredError as exc:
        return _gallery_not_configured_response(exc)

    content = await file.read()
    validation_error = _validate_upload(file, content)
    if validation_error:
        return validation_error

    filename = file.filename or "upload.jpg"
    try:
        file_id = await backend.send_photo(content, filename)
        thumb_url = await backend.get_file_url(file_id)
    except TelegramFileTooLargeError as exc:
        return err(413, str(exc), 413)
    except Exception as exc:
        _log.exception("failed to upload image to Telegram gallery")
        return err(500, f"telegram upload failed: {exc}", 500)

    image = gallery_store.add_image(
        account_id=account_id,
        file_id=file_id,
        filename=filename,
        size_bytes=len(content),
        mime_type=file.content_type or "image/jpeg",
        thumb_url=thumb_url,
        tags=[],
    )
    return JSONResponse({"code": 0, "data": with_stable_urls(image, request, account_id)})


@router.get("/gallery")
async def list_gallery_images(
    request: Request,
    authorization: str = Header(default=""),
    limit: int = 100,
    offset: int = 0,
) -> JSONResponse:
    """List the current user's gallery images with stable proxy URLs."""
    account = authorize(authorization)
    account_id = _account_id(account)
    if isinstance(account_id, JSONResponse):
        return account_id

    images = await list_images_for_app(
        account_id,
        request=request,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )
    total = gallery_store.count_images(account_id)
    return JSONResponse({"code": 0, "data": {"images": images, "count": len(images), "total": total}})


@router.delete("/gallery/{image_id}")
async def delete_gallery_image(image_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """Soft-delete a gallery image."""
    account = authorize(authorization)
    account_id = _account_id(account)
    if isinstance(account_id, JSONResponse):
        return account_id

    if gallery_store.delete_image(image_id, account_id):
        return JSONResponse({"code": 0, "data": {"deleted": True}})
    return err(404, "image not found", 404)


@router.get("/gallery/{image_id}/thumb")
async def get_gallery_thumb(
    image_id: str,
    authorization: str = Header(default=""),
    access_token: str = Query(default=""),
    fetch_token: str = Query(default=""),
    thumb_token: str = Query(default=""),
) -> Response:
    """Proxy gallery image bytes with a stable, cacheable URL."""
    return await _serve_gallery_proxy(
        image_id,
        authorization,
        access_token,
        fetch_token,
        thumb_token=thumb_token,
        for_file=False,
    )


@router.get("/gallery/{image_id}/file")
async def get_gallery_file(
    image_id: str,
    authorization: str = Header(default=""),
    access_token: str = Query(default=""),
    fetch_token: str = Query(default=""),
) -> Response:
    """Proxy full gallery image bytes for draw_from_image (no Telegram URL exposure)."""
    return await _serve_gallery_proxy(
        image_id,
        authorization,
        access_token,
        fetch_token,
        for_file=True,
    )


@router.get("/gallery/{image_id}/download")
async def get_gallery_download_url(
    image_id: str,
    request: Request,
    authorization: str = Header(default=""),
) -> JSONResponse:
    """Return a stable server proxy URL (never exposes Telegram bot token)."""
    account = authorize(authorization)
    account_id = _account_id(account)
    if isinstance(account_id, JSONResponse):
        return account_id

    image = gallery_store.get_image(image_id, account_id)
    if image is None:
        return err(404, "image not found", 404)

    return JSONResponse({"code": 0, "data": {"url": stable_file_download_url(request, account_id, image_id)}})
