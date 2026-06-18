"""Serve the 2D digital human (Live2D) frontend assets.

The original digital-human page lives in the legacy xiaozhi-esp32-server
submodule. It already supports LiMa's ``lima-device-v1`` WebSocket protocol,
so this module only needs to expose the static files and patch the default
connection URL so the page works out of the box when served from LiMa.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from device_gateway.auth import configured_device_tokens

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

    For limaWsUrl the value is always overwritten (forced) because the
    original HTML hardcodes ws://127.0.0.1:8080 which only works on localhost.
    Other fields are only set when empty so returning visitors keep their own
    settings after the first visit.
    """
    ws_url = 'proto + "//" + window.location.host + "/device/v1/ws"'

    def _js(value: str | bool) -> str:
        """JSON-encode a value for safe embedding inside a <script> tag."""
        text = json.dumps(value)
        # Escape the closing script tag sequence to prevent premature </script>.
        return re.sub(r"</script", r"<\\/script", text, flags=re.IGNORECASE)

    return f"""<script>
(function () {{
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  function setInput(id, value) {{
    const el = document.getElementById(id);
    if (el && !el.value.trim() && value) el.value = value;
  }}
  function forceSetInput(id, value) {{
    const el = document.getElementById(id);
    if (el && value) el.value = value;
  }}
  function seedStorage(key, value) {{
    try {{
      const stored = localStorage.getItem(key);
      if (value && (!stored || !stored.trim())) localStorage.setItem(key, value);
    }} catch (e) {{}}
  }}
  function apply() {{
    forceSetInput("limaWsUrl", {ws_url});
    setInput("deviceMac", {_js(device_id)});
    setInput("deviceName", {_js(device_name)});
    setInput("clientId", {_js(client_id)});
    setInput("limaToken", {_js(token)});
    seedStorage("xz_tester_deviceMac", {_js(device_id)});
    seedStorage("xz_tester_deviceName", {_js(device_name)});
    seedStorage("xz_tester_clientId", {_js(client_id)});
    seedStorage("xz_tester_limaToken", {_js(token)});
    const wwEnabled = document.getElementById("wakewordEnabled");
    if (wwEnabled && !wwEnabled.value) wwEnabled.value = {_js("true" if wakeword_enabled else "false")};
  }}
  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", apply);
  }} else {{
    apply();
  }}
}})();
</script>
"""


def _digital_human_defaults() -> dict[str, str | bool]:
    """Return default connection values from environment variables.

    Token is taken from LIMA_DEVICE_TOKENS if the default device_id is present
    there, so that the injected frontend token always matches the backend
    validator. Falls back to LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN for convenience.
    """
    device_id = os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID", "web-tester").strip()
    token = configured_device_tokens().get(device_id, "").strip()
    if not token:
        token = os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN", "").strip()
    return {
        "device_id": device_id,
        "device_name": os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_NAME", "LiMa 星云数字人").strip(),
        "client_id": os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_CLIENT_ID", "web_test_client").strip(),
        "token": token,
        "wakeword_enabled": os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_WAKEUP_WORD_ENABLED", "false").strip().lower()
        == "true",
    }


def _patch_index_html(content: str) -> str:
    """Inject auto-configuration script and brand patches into the digital-human index page."""
    # Replace brand in specific locations only (avoid breaking wake words that contain "小智")
    content = content.replace("<title>小智数字人页面</title>", "<title>LiMa 星云数字人页面</title>")
    content = content.replace("<div class=\"brand\">小智 AI 语音/视频通话</div>", "<div class=\"brand\">LiMa 星云 AI 语音/视频通话</div>")
    content = content.replace("小智数字人页面", "LiMa 星云数字人页面")
    content = content.replace("小智服务器", "星云服务器")
    content = content.replace("小智 OTA", "LiMa 星云 OTA")
    # Do NOT replace generic "小智" because wake words like "小智小智" must remain intact
    # Replace LiMa labels
    content = content.replace('"LiMa (直连)"', '"LiMa 星云 (直连)"')
    content = content.replace('>LiMa WebSocket 地址:<', '>LiMa 星云 WebSocket 地址:<')
    content = content.replace('"LiMa 认证令牌:"', '"LiMa 星云认证令牌:"')
    content = content.replace('placeholder="LiMa WebSocket地址', 'placeholder="LiMa 星云 WebSocket地址')
    defaults = _digital_human_defaults()
    script = _build_auto_config_script(**defaults)  # type: ignore[arg-type]
    marker = '<script type="module" src="js/app.js?v=0205"></script>'
    if marker in content:
        content = content.replace(marker, script + "\n    " + marker)
    else:
        content = content.replace("</body>", script + "</body>")
    token = str(defaults.get("token", ""))
    if token:
        escaped = html.escape(token, quote=True)
        content = re.sub(
            r'(<input\s+[^>]*id="limaToken"\s+[^>]*?)value=""',
            rf'\1value="{escaped}"',
            content,
        )
    return content


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


@router.get("/{path:path}")
async def serve_digital_human_static(path: str) -> FileResponse:
    """Serve the remaining static assets (JS/CSS/images) from the submodule."""
    if not _ASSETS_AVAILABLE:
        raise HTTPException(status_code=404, detail="Digital human assets not available")
    target = (_DH_DIR / path).resolve()
    try:
        target.relative_to(_DH_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(target)


def mount_static_files(app) -> None:
    """No-op: static assets are served by the catch-all router route.

    Kept for backward compatibility with server.py, which still calls this
    function after ``app.include_router(digital_human_router)``.
    """
    pass
