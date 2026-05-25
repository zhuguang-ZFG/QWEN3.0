"""Fetch iLink bot add-friend QR image bytes for outbound WeChat messages."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


async def fetch_invite_qr_png() -> tuple[bytes, str] | None:
    """
    Return (png_bytes, mime) or None.
    Uses local cache data/weixin_share_qr.json when fresh enough.
    """
    cache = Path(__file__).resolve().parent.parent / "data" / "weixin_share_qr.json"
    if cache.is_file():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            url = str(data.get("share_url") or "").strip()
            if url:
                got = await _download_image(url)
                if got:
                    return got
        except Exception as exc:
            log.debug("invite qr cache read failed: %s", exc)

    return await _fetch_live()


async def _fetch_live() -> tuple[bytes, str] | None:
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
        return None

    async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as session:
        qr_resp = await _api_get(
            session,
            base_url=ILINK_BASE_URL,
            endpoint=f"{EP_GET_BOT_QR}?bot_type=3",
            timeout_ms=QR_TIMEOUT_MS,
        )
    url = str(qr_resp.get("qrcode_img_content") or qr_resp.get("qrcode") or "").strip()
    if not url:
        return None
    return await _download_image(url)


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
