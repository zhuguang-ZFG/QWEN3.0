"""Static file routes for LiMa frontend assets."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

# Project root
_BASE_DIR = Path(__file__).resolve().parent.parent


def _chat_index_candidates() -> list[Path]:
    return [
        _BASE_DIR / "donglicao-site" / "chat.html",
        _BASE_DIR / "data" / "chat" / "index.html",
    ]


@router.get("/sw.js")
async def serve_service_worker():
    """Serve the Service Worker file."""
    file_path = _BASE_DIR / "data" / "chat" / "sw.js"
    if not file_path.exists():
        raise HTTPException(404, "Service Worker not found")

    return FileResponse(
        file_path,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/manifest.json")
async def serve_manifest():
    """Serve the PWA manifest file."""
    file_path = _BASE_DIR / "data" / "chat" / "manifest.json"
    if not file_path.exists():
        raise HTTPException(404, "Manifest not found")

    return FileResponse(file_path, media_type="application/json", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/")
async def serve_index():
    """Serve the main chat interface."""
    file_path = next((path for path in _chat_index_candidates() if path.exists()), None)
    if file_path is None:
        raise HTTPException(404, "Index not found")

    return FileResponse(file_path, media_type="text/html", headers={"Cache-Control": "no-cache"})


@router.get("/chat/admin.css")
async def serve_admin_css():
    """Serve the admin panel CSS."""
    file_path = _BASE_DIR / "data" / "chat" / "admin.css"
    if not file_path.exists():
        raise HTTPException(404, "Admin CSS not found")

    return FileResponse(file_path, media_type="text/css", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/chat/admin.js")
async def serve_admin_js():
    """Serve the admin panel JavaScript."""
    file_path = _BASE_DIR / "data" / "chat" / "admin.js"
    if not file_path.exists():
        raise HTTPException(404, "Admin JS not found")

    return FileResponse(
        file_path, media_type="application/javascript", headers={"Cache-Control": "public, max-age=3600"}
    )
