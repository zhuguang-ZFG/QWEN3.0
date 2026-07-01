"""Device app gallery routes backed by Telegram Bot storage.

Images are uploaded to Telegram; LiMa only stores file IDs and metadata.
If TELEGRAM_BOT_TOKEN is not configured, gallery endpoints return 503.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from device_gateway import gallery_store
from device_logic.auth import authorize
from device_logic.http import err
from integrations.telegram_bot.client import (
    TelegramBotClient,
    TelegramFileTooLargeError,
    TelegramNotConfiguredError,
)

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/device/v1/app", tags=["device-app-gallery"])

_ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _get_client() -> TelegramBotClient:
    """Return a configured TelegramBotClient or raise TelegramNotConfiguredError."""
    return TelegramBotClient()


def _account_id(account: dict[str, Any] | JSONResponse) -> str | JSONResponse:
    if isinstance(account, JSONResponse):
        return account
    return str(account.get("id", ""))


def _validate_upload(file: UploadFile, content: bytes) -> JSONResponse | None:
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        return err(400, f"unsupported content type: {file.content_type}", 400)
    if len(content) > _MAX_UPLOAD_BYTES:
        return err(413, f"file size exceeds {_MAX_UPLOAD_BYTES / 1024 / 1024}MB", 413)
    return None


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
        client = _get_client()
    except TelegramNotConfiguredError as exc:
        _log.warning("gallery upload rejected: %s", exc)
        return err(503, "gallery storage is not configured", 503)

    content = await file.read()
    validation_error = _validate_upload(file, content)
    if validation_error:
        return validation_error

    filename = file.filename or "upload.jpg"
    try:
        file_id = await client.send_photo(content, filename)
        thumb_url = await client.get_file_url(file_id)
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
    return JSONResponse({"code": 0, "data": image})


@router.get("/gallery")
async def list_gallery_images(
    authorization: str = Header(default=""),
    limit: int = 100,
    offset: int = 0,
) -> JSONResponse:
    """List the current user's gallery images."""
    account = authorize(authorization)
    account_id = _account_id(account)
    if isinstance(account_id, JSONResponse):
        return account_id

    images = gallery_store.list_images(account_id, limit=max(1, min(limit, 200)), offset=max(0, offset))
    return JSONResponse({"code": 0, "data": {"images": images, "count": len(images)}})


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


@router.get("/gallery/{image_id}/download")
async def get_gallery_download_url(image_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """Return a fresh Telegram download URL for a gallery image."""
    account = authorize(authorization)
    account_id = _account_id(account)
    if isinstance(account_id, JSONResponse):
        return account_id

    image = gallery_store.get_image(image_id, account_id)
    if image is None:
        return err(404, "image not found", 404)

    try:
        client = _get_client()
        url = await client.get_file_url(image["fileId"])
    except TelegramNotConfiguredError as exc:
        _log.warning("gallery download rejected: %s", exc)
        return err(503, "gallery storage is not configured", 503)
    except Exception as exc:
        _log.exception("failed to get Telegram download URL")
        return err(500, f"telegram download failed: {exc}", 500)

    return JSONResponse({"code": 0, "data": {"url": url}})
