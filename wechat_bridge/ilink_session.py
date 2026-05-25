"""iLink session keepalive and automatic QR re-login when token expires."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
RELONGIN_HTML = ROOT / "data" / "weixin_relogin_qr.html"
RELONGIN_STATUS = ROOT / "data" / "weixin_relogin_status.json"


def is_session_dead(ret: Any, errcode: Any, errmsg: Optional[str] = None) -> bool:
    try:
        from gateway.platforms.weixin import (
            SESSION_EXPIRED_ERRCODE,
            _is_stale_session_ret,
        )
    except ImportError:
        return ret == -14 or errcode == -14

    if ret == SESSION_EXPIRED_ERRCODE or errcode == SESSION_EXPIRED_ERRCODE:
        return True
    return _is_stale_session_ret(ret, errcode, errmsg)


def _write_relogin_html(qr_url: str, qr_token: str) -> Path:
    RELONGIN_HTML.parent.mkdir(parents=True, exist_ok=True)
    safe = qr_url.replace("&", "&amp;").replace('"', "&quot;")
    body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LiMa 微信 iLink 续登</title>
<meta http-equiv="refresh" content="30">
<style>body{{font-family:sans-serif;max-width:520px;margin:1.5rem auto;padding:1rem;line-height:1.6}}
.box{{background:#fff3cd;padding:1rem;border-radius:8px}}</style></head>
<body>
<h1>LiMa 微信会话需续登</h1>
<p class="box">请用<strong>管理员微信</strong>扫一扫下方链接（约 8 分钟内有效）：</p>
<p><a href="{safe}">{safe}</a></p>
<p>续登成功后 bridge 会自动恢复，无需重启 VPS。</p>
</body></html>"""
    RELONGIN_HTML.write_text(body, encoding="utf-8")
    return RELONGIN_HTML


def _write_status(**fields: object) -> None:
    RELONGIN_STATUS.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": int(time.time()), **fields}
    RELONGIN_STATUS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _merge_vps_env(account_id: str, token: str, base_url: str) -> None:
    if os.environ.get("LIMA_WEIXIN_VPS", "").strip() not in ("1", "true", "yes"):
        return
    snippet = Path("/opt/lima-router/data/weixin_ilink.env.snippet")
    env_path = Path("/opt/lima-router/.env")
    if not env_path.parent.exists():
        return
    lines = [
        f"WEIXIN_ACCOUNT_ID={account_id}",
        f"WEIXIN_TOKEN={token}",
        f"WEIXIN_BASE_URL={base_url}",
        "WEIXIN_DM_POLICY=open",
        "WEIXIN_GROUP_POLICY=disabled",
        "LIMA_CHANNEL_BASE_URL=http://127.0.0.1:8080",
    ]
    snippet.parent.mkdir(parents=True, exist_ok=True)
    snippet.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "merge_env",
            str(ROOT / "scripts" / "_merge_weixin_ilink_env_remote.py"),
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
    except Exception as exc:
        log.warning("env merge skipped: %s", exc)


async def keepalive_loop(
    session,
    *,
    base_url: str,
    token: str,
    account_id: str,
    user_id: str = "",
    stop: asyncio.Event,
) -> None:
    """Periodic getconfig ping to reduce idle session drop."""
    from gateway.platforms.weixin import _get_config, CONFIG_TIMEOUT_MS

    minutes = int(os.environ.get("LIMA_WEIXIN_KEEPALIVE_MIN", "18"))
    interval = max(5, minutes) * 60
    uid = user_id or account_id
    log.info("iLink keepalive every %d min", minutes)

    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            pass
        try:
            resp = await _get_config(
                session,
                base_url=base_url,
                token=token,
                user_id=uid,
                context_token=None,
            )
            ret = resp.get("ret", 0)
            errcode = resp.get("errcode", 0)
            if is_session_dead(ret, errcode, resp.get("errmsg")):
                log.warning("keepalive: session dead ret=%s errcode=%s", ret, errcode)
            else:
                log.debug("keepalive ok")
        except Exception as exc:
            log.warning("keepalive failed: %s", exc)


async def relogin_via_qr(
    hermes_home: str,
    *,
    timeout_seconds: int = 600,
) -> Optional[Dict[str, str]]:
    """Fetch QR, write HTML, poll until confirmed; persist new bot_token."""
    from gateway.platforms.weixin import (
        ILINK_BASE_URL,
        EP_GET_BOT_QR,
        EP_GET_QR_STATUS,
        QR_TIMEOUT_MS,
        save_weixin_account,
        _api_get,
        _make_ssl_connector,
        check_weixin_requirements,
    )
    import aiohttp

    if not check_weixin_requirements():
        return None

    _write_status(phase="fetching_qr")
    async with aiohttp.ClientSession(
        trust_env=True, connector=_make_ssl_connector()
    ) as session:
        qr_resp = await _api_get(
            session,
            base_url=ILINK_BASE_URL,
            endpoint=f"{EP_GET_BOT_QR}?bot_type=3",
            timeout_ms=QR_TIMEOUT_MS,
        )
        qrcode_value = str(qr_resp.get("qrcode") or "")
        qrcode_url = str(qr_resp.get("qrcode_img_content") or "")
        if not qrcode_value:
            _write_status(phase="error", msg="no_qrcode")
            return None

        scan_data = qrcode_url or qrcode_value
        html_path = _write_relogin_html(scan_data, qrcode_value)
        log.warning(
            "iLink session expired — scan QR to renew: %s (file %s)",
            scan_data[:80],
            html_path,
        )
        _write_status(phase="waiting_scan", html=str(html_path), url=scan_data[:200])

        deadline = time.monotonic() + timeout_seconds
        current_base = ILINK_BASE_URL
        while time.monotonic() < deadline:
            status_resp = await _api_get(
                session,
                base_url=current_base,
                endpoint=f"{EP_GET_QR_STATUS}?qrcode={qrcode_value}",
                timeout_ms=QR_TIMEOUT_MS,
            )
            status = str(status_resp.get("status") or "wait")
            if status == "confirmed":
                account_id = str(status_resp.get("ilink_bot_id") or "")
                token = str(status_resp.get("bot_token") or "")
                base_url = str(status_resp.get("baseurl") or ILINK_BASE_URL)
                if not account_id or not token:
                    _write_status(phase="error", msg="incomplete_creds")
                    return None
                save_weixin_account(
                    hermes_home,
                    account_id=account_id,
                    token=token,
                    base_url=base_url,
                    user_id=str(status_resp.get("ilink_user_id") or ""),
                )
                _merge_vps_env(account_id, token, base_url)
                _write_status(phase="ok", account_id=account_id)
                log.info("iLink relogin OK account=%s", account_id)
                return {
                    "account_id": account_id,
                    "token": token,
                    "base_url": base_url,
                    "user_id": str(status_resp.get("ilink_user_id") or ""),
                }
            if status == "expired":
                qr_resp = await _api_get(
                    session,
                    base_url=ILINK_BASE_URL,
                    endpoint=f"{EP_GET_BOT_QR}?bot_type=3",
                    timeout_ms=QR_TIMEOUT_MS,
                )
                qrcode_value = str(qr_resp.get("qrcode") or "")
                qrcode_url = str(qr_resp.get("qrcode_img_content") or "")
                scan_data = qrcode_url or qrcode_value
                _write_relogin_html(scan_data, qrcode_value)
            elif status == "scaned_but_redirect":
                host = str(status_resp.get("redirect_host") or "")
                if host:
                    current_base = f"https://{host}"
            await asyncio.sleep(2)

    _write_status(phase="timeout")
    return None


async def run_relogin_background(
    hermes_home: str,
    on_success: Callable[[Dict[str, str]], None],
) -> None:
    """Single-flight background relogin."""
    if os.environ.get("LIMA_WEIXIN_AUTO_RELOGIN", "1") != "1":
        log.error("auto relogin disabled (LIMA_WEIXIN_AUTO_RELOGIN=0)")
        return
    creds = await relogin_via_qr(hermes_home)
    if creds:
        on_success(creds)
