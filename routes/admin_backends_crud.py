"""Admin backend CRUD API (M13) — add/update/delete backends via overlay JSON.

Auth: verify_admin (all) + verify_csrf (mutating).
Storage: data/backend_overrides.json — non-destructive to backends_registry.py.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf
from backends_registry import BACKENDS, DISABLED_HOST_DEPENDENT_BACKENDS

router = APIRouter()
_log = logging.getLogger(__name__)

OVERLAY_PATH = Path(__file__).resolve().parent.parent / "data" / "backend_overrides.json"


def _read_overlay() -> dict:
    if not OVERLAY_PATH.exists():
        return {"add": {}, "update": {}, "delete": []}
    try:
        return json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"add": {}, "update": {}, "delete": []}


def _write_overlay(overlay: dict) -> None:
    OVERLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERLAY_PATH.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _describe_backend_list() -> list[dict]:
    """List all backends with their current status, including overlay state."""
    results = []
    all_names = set(BACKENDS.keys()) | set(DISABLED_HOST_DEPENDENT_BACKENDS.keys())
    overlay = _read_overlay()

    for name in sorted(all_names):
        cfg = BACKENDS.get(name) or DISABLED_HOST_DEPENDENT_BACKENDS.get(name, {})
        results.append({
            "name": name,
            "url": cfg.get("url", ""),
            "model": cfg.get("model", ""),
            "fmt": cfg.get("fmt", "openai"),
            "timeout": cfg.get("timeout", 30),
            "caps": cfg.get("caps", []),
            "admission": cfg.get("admission", ""),
            "private_code_allowed": cfg.get("private_code_allowed", False),
            "key_configured": bool(cfg.get("key", "") and cfg.get("key", "") not in ("none", "YOUR_KEY_HERE")),
            "in_registry": name in BACKENDS,
            "in_disabled": name in DISABLED_HOST_DEPENDENT_BACKENDS,
            "overlay_action": "added" if name in overlay.get("add", {}) else
                              "updated" if name in overlay.get("update", {}) else
                              "deleted" if name in overlay.get("delete", []) else "none",
        })

    # Also list overlay entries that aren't in BACKENDS/DISABLED (pending adds)
    for name, cfg in overlay.get("add", {}).items():
        if name not in all_names:
            results.append({
                "name": name,
                "url": cfg.get("url", ""),
                "model": cfg.get("model", ""),
                "fmt": cfg.get("fmt", "openai"),
                "timeout": cfg.get("timeout", 30),
                "caps": cfg.get("caps", []),
                "admission": "",
                "private_code_allowed": False,
                "key_configured": bool(cfg.get("key", "")),
                "in_registry": False,
                "in_disabled": False,
                "overlay_action": "added",
                "pending": True,
            })

    return results


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/admin/backends", dependencies=[Depends(verify_admin)])
async def list_backends():
    """List all backends with overlay status."""
    return {"ok": True, "backends": _describe_backend_list(), "total": len(BACKENDS)}


@router.post("/admin/backends", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def add_backend(body: dict):
    """Add a new backend via overlay."""
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")
    overlay = _read_overlay()

    # Remove from delete list if previously deleted
    if name in overlay.get("delete", []):
        overlay["delete"].remove(name)

    overlay.setdefault("add", {})[name] = {
        "url": body.get("url", ""),
        "key": body.get("key", "none"),
        "model": body.get("model", ""),
        "fmt": body.get("fmt", "openai"),
        "timeout": int(body.get("timeout", 30)),
        "caps": body.get("caps", []),
    }
    _write_overlay(overlay)
    _log.info("admin: added backend %s", name)
    return {"ok": True, "name": name}


@router.put("/admin/backends/{name}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def update_backend(name: str, body: dict):
    """Update an existing backend via overlay."""
    if name not in BACKENDS and name not in DISABLED_HOST_DEPENDENT_BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    overlay = _read_overlay()
    overlay.setdefault("update", {})[name] = {k: v for k, v in body.items() if k in (
        "url", "key", "model", "fmt", "timeout", "caps", "admission", "private_code_allowed"
    )}
    _write_overlay(overlay)
    _log.info("admin: updated backend %s", name)
    return {"ok": True, "name": name}


@router.delete("/admin/backends/{name}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def delete_backend(name: str):
    """Delete a backend by adding it to the overlay delete list."""
    overlay = _read_overlay()
    if name not in overlay.get("delete", []):
        overlay.setdefault("delete", []).append(name)
    # Clean up any add/update entries for this backend
    overlay.get("add", {}).pop(name, None)
    overlay.get("update", {}).pop(name, None)
    _write_overlay(overlay)
    _log.info("admin: deleted backend %s", name)
    return {"ok": True, "name": name}


@router.post("/admin/backends/{name}/test", dependencies=[Depends(verify_admin)])
async def test_backend(name: str):
    """Test backend connectivity with a simple chat probe."""
    import time
    import urllib.request

    cfg = BACKENDS.get(name) or DISABLED_HOST_DEPENDENT_BACKENDS.get(name)
    if not cfg:
        raise HTTPException(404, f"backend '{name}' not found")

    url = cfg.get("url", "")
    key = cfg.get("key", "")
    model = cfg.get("model", "")
    started = time.time()
    try:
        payload = json.dumps({
            "model": model,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "hi"}],
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }, method="POST")
        resp = urllib.request.urlopen(req, timeout=15)
        elapsed = int((time.time() - started) * 1000)
        return {"ok": True, "latency_ms": elapsed, "status": resp.status}
    except Exception as exc:
        elapsed = int((time.time() - started) * 1000)
        return {"ok": False, "latency_ms": elapsed, "error": str(exc)[:200]}
