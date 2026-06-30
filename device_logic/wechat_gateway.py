"""WeChat mini-program server-side gateway (jscode2session)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_JS_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


class WechatLoginError(Exception):
    """Raised when WeChat jscode2session returns an error or network fails."""


class WechatMiniappGateway:
    """Call WeChat mini-program server APIs with appid/secret."""

    def __init__(self, appid: str, secret: str, timeout: float = 10.0) -> None:
        self.appid = appid
        self.secret = secret
        self.timeout = timeout

    async def jscode2session(self, code: str) -> dict[str, Any]:
        """Exchange a login code for openid, session_key and optional unionid."""
        if not self.appid or not self.secret:
            raise WechatLoginError("WeChat mini-program appid/secret not configured")

        params = {
            "appid": self.appid,
            "secret": self.secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        try:
            import time

            start = time.monotonic()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(_JS_CODE2SESSION_URL, params=params)
                response.raise_for_status()
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info("WeChat jscode2session took %.1fms", elapsed_ms)
        except httpx.HTTPError as exc:
            logger.warning("WeChat jscode2session request failed: %s", exc)
            raise WechatLoginError("WeChat login request failed") from exc

        data = response.json()
        errcode = data.get("errcode")
        if errcode:
            errmsg = data.get("errmsg", "unknown WeChat error")
            logger.warning("WeChat jscode2session error: %s %s", errcode, errmsg)
            raise WechatLoginError(f"WeChat login failed: {errmsg}")

        openid = data.get("openid")
        if not openid:
            raise WechatLoginError("WeChat response missing openid")

        return {
            "openid": openid,
            "session_key": data.get("session_key", ""),
            "unionid": data.get("unionid", ""),
        }
