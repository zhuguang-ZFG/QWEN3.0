"""Serve the 2D digital human (Live2D) frontend assets.

The original digital-human page lives in the legacy xiaozhi-esp32-server
submodule. It already supports LiMa's ``lima-device-v1`` WebSocket protocol,
so this module only needs to expose the static files and patch the default
connection URL so the page works out of the box when served from LiMa.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

_log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DH_DIR = _PROJECT_ROOT / "esp32S_XYZ" / "server" / "xiaozhi-esp32-server" / "main" / "digital-human"
_FALLBACK_DH_DIR = _PROJECT_ROOT / "data" / "digital-human"


def _resolve_assets() -> tuple[Path, Path] | None:
    """Return (directory, index_path) if digital-human assets are available."""
    candidates = [_DEFAULT_DH_DIR, _FALLBACK_DH_DIR]
    env_dir = os.environ.get("LIMA_DIGITAL_HUMAN_DIR", "").strip()
    if env_dir:
        candidates.insert(0, Path(env_dir))
    for directory in candidates:
        index_path = directory / "index.html"
        if index_path.exists():
            return directory, index_path
    return None


_resolved = _resolve_assets()
if _resolved is not None:
    _DH_DIR, _INDEX_PATH = _resolved
    _ASSETS_AVAILABLE = True
else:
    _DH_DIR = _DEFAULT_DH_DIR
    _INDEX_PATH = _DEFAULT_DH_DIR / "index.html"
    _ASSETS_AVAILABLE = False
    _log.warning(
        "Digital human assets not found at %s or %s; /digital-human/ will be unavailable.",
        _DEFAULT_DH_DIR,
        _FALLBACK_DH_DIR,
    )


def _build_auto_config_script(
    *,
    device_id: str,
    device_name: str,
    client_id: str,
    token: str,
    wakeword_enabled: bool,
) -> str:
    """Return an inline script that pre-fills LiMa connection defaults.

    Defaults are only applied when the corresponding field/localStorage entry
    is empty, so returning visitors keep their own settings after the first
    visit.
    """
    ws_url = '" + proto + "//" + window.location.host + "/device/v1/ws"'
    return f"""<script>
(function () {{
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  function setInput(id, value) {{
    const el = document.getElementById(id);
    if (el && !el.value && value) el.value = value;
  }}
  function seedStorage(key, value) {{
    try {{
      if (value && !localStorage.getItem(key)) localStorage.setItem(key, value);
    }} catch (e) {{}}
  }}
  setInput("limaWsUrl", {ws_url});
  setInput("deviceMac", {json.dumps(device_id)});
  setInput("deviceName", {json.dumps(device_name)});
  setInput("clientId", {json.dumps(client_id)});
  setInput("limaToken", {json.dumps(token)});
  seedStorage("xz_tester_deviceMac", {json.dumps(device_id)});
  seedStorage("xz_tester_deviceName", {json.dumps(device_name)});
  seedStorage("xz_tester_clientId", {json.dumps(client_id)});
  seedStorage("xz_tester_limaToken", {json.dumps(token)});
  const wwEnabled = document.getElementById("wakewordEnabled");
  if (wwEnabled && !wwEnabled.value) wwEnabled.value = {json.dumps("true" if wakeword_enabled else "false")};
}})();
</script>
"""


def _digital_human_defaults() -> dict[str, str | bool]:
    """Return default connection values from environment variables."""
    return {
        "device_id": os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID", "web-tester").strip(),
        "device_name": os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_NAME", "Web 数字人").strip(),
        "client_id": os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_CLIENT_ID", "web_test_client").strip(),
        "token": os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN", "").strip(),
        "wakeword_enabled": os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_WAKEUP_WORD_ENABLED", "false").strip().lower() == "true",
    }


def _patch_index_html(content: str) -> str:
    """Inject auto-configuration script into the digital-human index page."""
    script = _build_auto_config_script(**_digital_human_defaults())  # type: ignore[arg-type]
    marker = '<script type="module" src="js/app.js?v=0205"></script>'
    if marker in content:
        return content.replace(marker, script + "\n    " + marker)
    return content.replace("</body>", script + "</body>")


router = APIRouter(prefix="/digital-human")


@router.get("/")
@router.get("/index.html")
async def serve_digital_human_index() -> HTMLResponse:
    """Serve the patched digital-human page."""
    if not _ASSETS_AVAILABLE or not _INDEX_PATH.exists():
        raise HTTPException(status_code=404, detail="Digital human page not found")
    content = _INDEX_PATH.read_text(encoding="utf-8")
    return HTMLResponse(_patch_index_html(content), media_type="text/html")


@router.get("/health")
async def digital_human_health() -> dict[str, str]:
    """Return the availability and resolved path of digital-human assets."""
    return {
        "status": "ok" if _ASSETS_AVAILABLE else "unavailable",
        "static_path": str(_DH_DIR),
        "index_exists": str(_INDEX_PATH.exists()),
    }


def mount_static_files(app) -> None:
    """Mount the digital-human static directory on the FastAPI app.

    This must be called *after* ``app.include_router(digital_human_router)``
    so the index/health endpoints take precedence over the catch-all static
    mount.
    """
    if _ASSETS_AVAILABLE:
        app.mount("/digital-human", StaticFiles(directory=_DH_DIR), name="digital_human_static")
