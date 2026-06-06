"""Admin config import/export endpoints (extracted from admin_api)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()
_log = logging.getLogger(__name__)

_CONFIG_EXPORT_VERSION = "1.0"
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_OVERLAY_PATH = _DATA_DIR / "backend_overrides.json"
_ADMIT_PATH = _DATA_DIR / "backend_admission.json"


@router.get("/api/config/export", dependencies=[Depends(verify_admin)])
async def admin_config_export():
    """Export backend overrides and admission config as a single JSON blob."""
    config: dict = {
        "version": _CONFIG_EXPORT_VERSION,
        "exported_at": time.time(),
        "backend_overrides": {},
        "backend_admission": {},
    }
    if _OVERLAY_PATH.exists():
        try:
            config["backend_overrides"] = json.loads(
                _OVERLAY_PATH.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            pass
    if _ADMIT_PATH.exists():
        try:
            config["backend_admission"] = json.loads(
                _ADMIT_PATH.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            pass
    return config


@router.post("/api/config/import", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_config_import(body: dict):
    """Import backend overrides and admission config from a JSON payload."""
    version = body.get("version", "")
    if version != _CONFIG_EXPORT_VERSION:
        raise HTTPException(
            422,
            f"Unsupported config version: {version!r} (expected {_CONFIG_EXPORT_VERSION})",
        )
    imported: list[str] = []
    overrides = body.get("backend_overrides")
    if isinstance(overrides, dict):
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _OVERLAY_PATH.write_text(
            json.dumps(overrides, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        imported.append("backend_overrides")
    admission = body.get("backend_admission")
    if isinstance(admission, dict):
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _ADMIT_PATH.write_text(
            json.dumps(admission, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        imported.append("backend_admission")
    _log.info("admin: config imported sections=%s", imported)
    try:
        from backends_registry import _load_backend_overlay
        _load_backend_overlay()
        _log.info("admin: backends reloaded after config import")
    except ImportError:
        _log.warning("admin: backends_registry not available, config requires restart")
    return {"ok": True, "imported": imported}
