"""File upload endpoint for manager-mobile and other clients."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from routes.upload_tokens import public_upload_get_enabled, upload_access_token, verify_upload_access_token
from routes.xiaozhi_compat.auth import authorize

logger = logging.getLogger(__name__)

router = APIRouter()

_BASE_DIR = Path(__file__).resolve().parent.parent
_UPLOAD_DIR = _BASE_DIR / "data" / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "webp", "gif"})
_MAX_SIZE_BYTES = 5 * 1024 * 1024
_STORED_NAME_RE = re.compile(r"^[a-f0-9]{32}\.[a-z0-9]+$")
_AUDIO_EXTENSIONS = frozenset({"wav", "mp3", "m4a"})

_IMAGE_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF87a", b"GIF89a"),
    "webp": (b"RIFF",),
}

_MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}


def _extension(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def _is_allowed(filename: str) -> bool:
    return _extension(filename) in _ALLOWED_EXTENSIONS


def _matches_image_signature(content: bytes, ext: str) -> bool:
    signatures = _IMAGE_SIGNATURES.get(ext, ())
    if not signatures:
        return False
    if ext == "webp":
        return content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP"
    return any(content.startswith(sig) for sig in signatures)


def _safe_upload_path(filename: str, *, allowed_extensions: frozenset[str] | None = None) -> Path | None:
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    if not _STORED_NAME_RE.fullmatch(filename):
        return None
    ext = _extension(filename)
    allowed = allowed_extensions or _ALLOWED_EXTENSIONS
    if ext not in allowed:
        return None
    base = _UPLOAD_DIR.resolve()
    candidate = (base / filename).resolve()
    if not candidate.is_file() or not candidate.is_relative_to(base):
        return None
    return candidate


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    authorization: str = Header(default=""),
) -> JSONResponse:
    """Upload an image file and return its public URL."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    if not file.filename:
        return JSONResponse({"code": 400, "message": "filename is required"}, status_code=400)

    ext = _extension(file.filename)
    if ext not in _ALLOWED_EXTENSIONS:
        return JSONResponse(
            {"code": 400, "message": f"file type not allowed: {ext}"},
            status_code=400,
        )

    content = await file.read()
    if len(content) > _MAX_SIZE_BYTES:
        return JSONResponse(
            {"code": 413, "message": f"file size exceeds {_MAX_SIZE_BYTES / 1024 / 1024}MB"},
            status_code=413,
        )

    if not _matches_image_signature(content, ext):
        return JSONResponse({"code": 400, "message": "file content does not match image type"}, status_code=400)

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    stored_path = _UPLOAD_DIR / stored_name
    stored_path.write_bytes(content)

    base_url = f"{request.url.scheme}://{request.url.netloc}"
    token = upload_access_token(stored_name)
    public_url = f"{base_url}/uploads/{stored_name}?token={token}"
    logger.info("uploaded file %s -> %s", file.filename, stored_name)

    return JSONResponse(
        {
            "code": 0,
            "message": "ok",
            "data": {
                "url": public_url,
                "name": stored_name,
                "size": len(content),
                "token": token,
            },
        }
    )


def _upload_get_allowed(filename: str, token: str, authorization: str) -> bool:
    if public_upload_get_enabled():
        return True
    if token and verify_upload_access_token(filename, token):
        return True
    account = authorize(authorization)
    return not isinstance(account, JSONResponse)


@router.get("/uploads/{filename}", response_model=None)
async def serve_uploaded_file(
    filename: str,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
):
    """Serve a previously uploaded file."""
    file_path = _safe_upload_path(filename)
    if file_path is None:
        return JSONResponse({"code": 404, "message": "file not found"}, status_code=404)

    if not _upload_get_allowed(filename, token, authorization):
        return JSONResponse({"code": 401, "message": "unauthorized"}, status_code=401)

    media_type = _MEDIA_TYPES.get(_extension(filename), "application/octet-stream")
    return FileResponse(file_path, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})
