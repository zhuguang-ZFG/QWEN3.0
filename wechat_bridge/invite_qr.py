"""Fetch iLink bot add-friend QR image bytes for outbound WeChat messages."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

QR_CACHE_TTL_SEC = int(os.environ.get("LIMA_WEIXIN_QR_CACHE_SEC", "21600"))


def _qr_cache_paths() -> list[Path]:
    roots = [
        Path(os.environ.get("LIMA_ROUTER_ROOT", "/opt/lima-router")),
        Path(__file__).resolve().parent.parent,
    ]
    return [r / "data" / "weixin_share_qr.json" for r in roots]


def _primary_cache_path() -> Path:
    return _qr_cache_paths()[0]


def _cache_age_ok(data: dict, *, allow_stale: bool = False) -> bool:
    if allow_stale:
        return bool(str(data.get("share_url") or "").strip())
    ts = int(data.get("ts") or 0)
    if ts <= 0:
        return False
    return (time.time() - ts) < QR_CACHE_TTL_SEC


def _read_cache(*, allow_stale: bool = False) -> dict | None:
    for cache in _qr_cache_paths():
        if not cache.is_file():
            continue
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if _cache_age_ok(data, allow_stale=allow_stale):
                return data
        except Exception as exc:
            log.debug("share url cache read failed: %s", exc)
    return None


def load_cached_share_url(*, allow_stale: bool = False) -> str:
    data = _read_cache(allow_stale=allow_stale)
    if not data:
        return ""
    return str(data.get("share_url") or "").strip()


def _write_cache(share_url: str, account_id: str = "") -> None:
    if not share_url:
        return
    path = _primary_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": int(time.time()),
        "account_id": account_id,
        "share_url": share_url,
        "html": str(path.parent / "weixin_share_qr.html"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("weixin share QR cache updated ts=%s", payload["ts"])


def _active_account_id() -> str:
    env_id = os.environ.get("WEIXIN_ACCOUNT_ID", "").strip()
    if env_id:
        return env_id
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "weixin" / "accounts"
    for path in sorted(home.glob("*.json")):
        if "context" in path.name or "sync" in path.name:
            continue
        return path.stem
    return ""


async def refresh_share_qr_cache(*, account_id: str = "") -> str:
    """Fetch add-friend URL and persist; always tags cache with the live bridge account."""
    aid = (account_id or _active_account_id()).strip()
    url = await _fetch_live_share_url()
    if url:
        _write_cache(url, aid)
    return url


async def fetch_invite_qr_png(*, account_id: str = "") -> tuple[bytes, str] | None:
    """Return (png_bytes, mime) or None. Always tries a fresh iLink URL first."""
    url = await refresh_share_qr_cache(account_id=account_id)
    if not url:
        url = load_cached_share_url(allow_stale=True)
    if not url:
        return None
    return await _download_image(url)


async def _fetch_live_share_url() -> str:
    from gateway.platforms.weixin import (
        ILINK_BASE_URL,
        EP_GET_BOT_QR,
        QR_TIMEOUT_MS,
        _api_get,
        _make_ssl_connector,
        check_weixin_requirements,
    )
    import aiohttp

    if not check_weixin_requirements():
        return ""

    async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as session:
        qr_resp = await _api_get(
            session,
            base_url=ILINK_BASE_URL,
            endpoint=f"{EP_GET_BOT_QR}?bot_type=3",
            timeout_ms=QR_TIMEOUT_MS,
        )
    return str(qr_resp.get("qrcode_img_content") or qr_resp.get("qrcode") or "").strip()


async def _download_image(url: str) -> tuple[bytes, str] | None:
    import aiohttp

    if url.startswith("data:image"):
        import base64

        try:
            _hdr, b64 = url.split(",", 1)
            mime = "image/png"
            if "jpeg" in _hdr or "jpg" in _hdr:
                mime = "image/jpeg"
            return base64.b64decode(b64), mime
        except Exception:
            return None

    if not url.startswith(("http://", "https://")):
        return None

    try:
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
                ctype = (resp.headers.get("Content-Type") or "image/png").split(";")[0]
                if not data or len(data) < 100:
                    return None
                return data, ctype
    except Exception as exc:
        log.warning("invite qr download failed: %s", exc)
        return None
