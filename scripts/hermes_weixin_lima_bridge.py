#!/usr/bin/env python3
"""Weixin iLink long-poll -> LiMa /channel/v1/wechat (not Hermes Agent brain)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("lima-weixin-bridge")

_WX_CHUNK = 3600


def _user_facing_error(err: str) -> str:
    if not err:
        return "暂时无法回复，请稍后再试。"
    low = err.lower()
    if "duplicate" in low:
        return ""
    if "401" in err or "403" in err:
        return "服务认证异常，请联系管理员检查 LiMa 令牌。"
    if err.startswith("HTTP 5") or "502" in err or "503" in err:
        return "LiMa 服务繁忙，请稍后再试。"
    if err.startswith("HTTP"):
        return "网络异常，请稍后再试。"
    if "timeout" in low or "timed out" in low:
        return "回复超时，请缩短问题或稍后再试。"
    return f"暂时无法处理：{err[:180]}"


def _split_reply(text: str, *, chunk: int = _WX_CHUNK) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk:
        return [text]
    parts: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk, n)
        if end < n:
            cut = text.rfind("\n", start, end)
            if cut > start + 200:
                end = cut + 1
        parts.append(text[start:end].rstrip())
        start = end
    numbered = []
    total = len(parts)
    for i, part in enumerate(parts, 1):
        if total > 1:
            numbered.append(f"({i}/{total})\n{part}")
        else:
            numbered.append(part)
    return numbered


def _load_weixin_account() -> tuple[str, str, str, str]:
    custom = os.environ.get("WEIXIN_ACCOUNT_DIR", "").strip()
    if custom:
        home = Path(custom)
    else:
        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "weixin" / "accounts"
    files = sorted(home.glob("*.json"))
    files = [f for f in files if "context" not in f.name and "sync" not in f.name]
    if not files:
        raise SystemExit(f"No Weixin account under {home}; run hermes_weixin_qr_login.py first")
    path = files[0]
    data = json.loads(path.read_text(encoding="utf-8"))
    account_id = path.stem
    token = str(data.get("token") or "").strip()
    base_url = str(data.get("base_url") or "https://ilinkai.weixin.qq.com").strip()
    if not token:
        raise SystemExit(f"Missing token in {path}")
    user_id = str(data.get("user_id") or "").strip()
    return account_id, token, base_url, user_id


def _sidecar_token() -> str:
    """VPS uses .env only; dev Windows may SSH-fetch token once."""
    token = os.environ.get("LIMA_WECHAT_SIDECAR_TOKEN", "").strip()
    if token:
        return token
    if os.environ.get("LIMA_WEIXIN_VPS", "").strip() in ("1", "true", "yes"):
        raise SystemExit("LIMA_WECHAT_SIDECAR_TOKEN missing in VPS .env")
    return _fetch_vps_sidecar_token_ssh()


def _fetch_vps_sidecar_token_ssh() -> str:
    key = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
    server = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
    remote = os.environ.get("LIMA_REMOTE_DIR", "/opt/lima-router")
    try:
        import paramiko
    except ImportError:
        raise SystemExit("pip install paramiko or set LIMA_WECHAT_SIDECAR_TOKEN")
    if not os.path.isfile(key):
        raise SystemExit(f"SSH key not found: {key}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(server, username="root", key_filename=key, timeout=60)
    _i, o, _e = ssh.exec_command(
        f"grep '^LIMA_WECHAT_SIDECAR_TOKEN=' {remote}/.env | cut -d= -f2-",
        timeout=30,
    )
    token = o.read().decode().strip()
    ssh.close()
    if not token:
        raise SystemExit("LIMA_WECHAT_SIDECAR_TOKEN missing on VPS .env")
    return token


class LimaWeixinBridge:
    """Minimal iLink poller wired to LiMa channel + plain text replies."""

    def __init__(
        self,
        *,
        account_id: str,
        token: str,
        base_url: str,
        lima_base: str,
        lima_token: str,
    ) -> None:
        self.account_id = account_id
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.lima_base = lima_base.rstrip("/")
        self.lima_token = lima_token
        self._running = True
        self._user_id = ""
        self._relogin_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def apply_credentials(
        self,
        *,
        account_id: str,
        token: str,
        base_url: str,
        user_id: str = "",
    ) -> None:
        self.account_id = account_id
        self.token = token
        self.base_url = base_url.rstrip("/")
        self._user_id = user_id

    async def _relogin_flow(self, hermes_home: str) -> None:
        from wechat_bridge.ilink_session import relogin_via_qr

        creds = await relogin_via_qr(hermes_home)
        if creds:
            self.apply_credentials(
                account_id=creds["account_id"],
                token=creds["token"],
                base_url=creds["base_url"],
                user_id=creds.get("user_id", ""),
            )
            log.info("credentials reloaded after QR relogin")

    def _schedule_relogin(self, hermes_home: str) -> None:
        if os.environ.get("LIMA_WEIXIN_AUTO_RELOGIN", "1") != "1":
            log.error(
                "session expired; set LIMA_WEIXIN_AUTO_RELOGIN=1 or scan QR manually"
            )
            return
        if self._relogin_task and not self._relogin_task.done():
            return
        self._relogin_task = asyncio.create_task(self._relogin_flow(hermes_home))

    async def run(self) -> None:
        from gateway.platforms.weixin import (
            check_weixin_requirements,
            _get_updates,
            _load_sync_buf,
            _save_sync_buf,
            _guess_chat_type,
            _make_ssl_connector,
            WEIXIN_CDN_BASE_URL,
            LONG_POLL_TIMEOUT_MS,
            MAX_CONSECUTIVE_FAILURES,
            RETRY_DELAY_SECONDS,
            BACKOFF_DELAY_SECONDS,
            send_weixin_direct,
        )
        import aiohttp
        from gateway.platforms.helpers import MessageDeduplicator
        from hermes_constants import get_hermes_home

        if not check_weixin_requirements():
            raise SystemExit("pip install aiohttp cryptography")

        from wechat_bridge.ilink_session import is_session_dead, keepalive_loop
        from wechat_bridge.lima_client import post_wechat_message
        from wechat_bridge.typing_helper import hide_typing, show_typing
        from wechat_bridge.weixin_inbound import collect_weixin_message

        hermes_home = str(get_hermes_home())
        self._stop.clear()
        dedup = MessageDeduplicator(ttl_seconds=300)
        sync_buf = _load_sync_buf(hermes_home, self.account_id)
        timeout_ms = LONG_POLL_TIMEOUT_MS
        consecutive_failures = 0
        cdn_base = os.environ.get("WEIXIN_CDN_BASE_URL", WEIXIN_CDN_BASE_URL)
        extra = {
            "account_id": self.account_id,
            "token": self.token,
            "base_url": self.base_url,
            "cdn_base_url": cdn_base,
        }

        log.info("LiMa Weixin bridge account=%s lima=%s", self.account_id, self.lima_base)

        from wechat_bridge.weixin_adapter import clear_live_adapter, ensure_live_adapter

        async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as session:
            ensure_live_adapter(
                session=session,
                token=self.token,
                account_id=self.account_id,
                base_url=self.base_url,
                cdn_base_url=cdn_base,
                extra=extra,
            )
            keepalive = asyncio.create_task(
                keepalive_loop(
                    session,
                    base_url=self.base_url,
                    token=self.token,
                    account_id=self.account_id,
                    user_id=self._user_id,
                    stop=self._stop,
                )
            )
            try:
                while self._running:
                    try:
                        response = await _get_updates(
                            session,
                            base_url=self.base_url,
                            token=self.token,
                            sync_buf=sync_buf,
                            timeout_ms=timeout_ms,
                        )
                        ret = response.get("ret", 0)
                        errcode = response.get("errcode", 0)
                        errmsg = response.get("errmsg")
                        if ret not in {0, None} or errcode not in {0, None}:
                            if is_session_dead(ret, errcode, errmsg):
                                log.warning(
                                    "iLink session dead (ret=%s errcode=%s); auto QR relogin",
                                    ret,
                                    errcode,
                                )
                                self._schedule_relogin(hermes_home)
                                await asyncio.sleep(15)
                                continue
                            consecutive_failures += 1
                            await asyncio.sleep(
                                BACKOFF_DELAY_SECONDS
                                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES
                                else RETRY_DELAY_SECONDS
                            )
                            continue
                        consecutive_failures = 0
                        new_buf = str(response.get("get_updates_buf") or "")
                        if new_buf:
                            sync_buf = new_buf
                            _save_sync_buf(hermes_home, self.account_id, sync_buf)

                        for message in response.get("msgs") or []:
                            sender_id = str(message.get("from_user_id") or "").strip()
                            if not sender_id or sender_id == self.account_id:
                                continue
                            message_id = str(message.get("message_id") or "").strip()
                            if message_id and dedup.is_duplicate(message_id):
                                continue
                            text, attachments = await collect_weixin_message(
                                session,
                                message,
                                cdn_base_url=cdn_base,
                            )
                            if not text and not attachments:
                                continue
                            chat_type, chat_id = _guess_chat_type(message, self.account_id)
                            if chat_type == "group":
                                continue

                            from wechat_bridge.context_tokens import save_from_message

                            save_from_message(self.account_id, message)

                            lima_mid = (
                                f"ilink-{sender_id}-{message_id or 'noid'}-"
                                f"{hashlib.sha256(text.encode()).hexdigest()[:12]}-"
                                f"{time.time_ns()}"
                            )
                            log.info(
                                "inbound from=%s text=%s att=%d",
                                sender_id[:12],
                                (text or "")[:40],
                                len(attachments),
                            )
                            chat_id_use = chat_id or sender_id
                            await show_typing(
                                session,
                                base_url=self.base_url,
                                token=self.token,
                                chat_id=chat_id_use,
                                message=message,
                            )
                            try:
                                result = post_wechat_message(
                                    base_url=self.lima_base,
                                    sidecar_token=self.lima_token,
                                    message_id=lima_mid,
                                    sender_id=sender_id,
                                    conversation_id=chat_id or sender_id,
                                    text=text or "",
                                    timestamp=int(time.time()),
                                    attachments=attachments or None,
                                )
                                reply = ""
                                if result.get("ok") and isinstance(result.get("reply"), dict):
                                    reply = str(result["reply"].get("text") or "")
                                elif result.get("error") == "duplicate message":
                                    log.info("skip duplicate inbound mid=%s", lima_mid[:48])
                                    continue
                                elif result.get("error"):
                                    reply = _user_facing_error(str(result["error"]))
                                if not reply:
                                    if result.get("ok"):
                                        continue
                                    reply = "暂时没有回复，请发送 /help 或稍后再试。"
                                reply_payload = (
                                    result["reply"]
                                    if isinstance(result.get("reply"), dict)
                                    else {"text": reply}
                                )
                                if "text" not in reply_payload:
                                    reply_payload["text"] = reply
                                from wechat_bridge.weixin_outbound import (
                                    deliver_channel_reply,
                                )

                                await deliver_channel_reply(
                                    session=session,
                                    extra=extra,
                                    token=self.token,
                                    chat_id=chat_id_use,
                                    reply=reply_payload,
                                    split_fn=_split_reply,
                                )
                                log.info(
                                    "replied ok=%s qr=%s voice=%s",
                                    result.get("ok"),
                                    bool(reply_payload.get("send_invite_qr")),
                                    bool(reply_payload.get("voice_reply_text")),
                                )
                            finally:
                                await hide_typing(
                                    session,
                                    base_url=self.base_url,
                                    token=self.token,
                                    chat_id=chat_id_use,
                                )
                    except asyncio.CancelledError:
                        break
                    except Exception as exc:
                        log.exception("poll error: %s", exc)
                        await asyncio.sleep(5)
            finally:
                clear_live_adapter(self.token)
                self._stop.set()
                keepalive.cancel()
                try:
                    await keepalive
                except asyncio.CancelledError:
                    pass


async def _main() -> None:
    account_id, token, base_url, user_id = _load_weixin_account()
    lima_token = _sidecar_token()
    lima_base = os.environ.get("LIMA_CHANNEL_BASE_URL", "http://127.0.0.1:8080")
    bridge = LimaWeixinBridge(
        account_id=account_id,
        token=token,
        base_url=base_url,
        lima_base=lima_base,
        lima_token=lima_token,
    )
    bridge._user_id = user_id
    await bridge.run()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
