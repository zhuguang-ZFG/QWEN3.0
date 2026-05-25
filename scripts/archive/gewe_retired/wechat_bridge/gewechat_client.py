"""Minimal Gewechat HTTP client (self-hosted :2531/v2/api)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional


def is_geweapi_cloud(base_url: str) -> bool:
    return "geweapi.com" in (base_url or "").lower()


class GewechatClient:
    def __init__(self, base_url: str, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self.cloud = is_geweapi_cloud(self.base_url)

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        payload = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-GEWE-TOKEN"] = self.token
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def fetch_token(self) -> str:
        if self.cloud:
            if not self.token:
                raise RuntimeError(
                    "GeWeAPI cloud requires GEWECHAT_TOKEN from manager.geweapi.com Token center"
                )
            return self.token
        raw = self._post("tools/getTokenId", {})
        if raw.get("ret") != 200:
            raise RuntimeError(raw.get("msg", "getTokenId failed"))
        token = raw.get("data", "")
        if not isinstance(token, str) or not token:
            raise RuntimeError("empty gewechat token")
        self.token = token
        return token

    def get_login_qr(
        self,
        app_id: str = "",
        region_id: str = "330000",
        *,
        retries: int = 1,
        retry_sleep_s: float = 2.0,
    ) -> dict:
        body: dict[str, Any] = {"appId": app_id or "", "regionId": region_id, "proxyIp": ""}
        if not self.cloud:
            body["type"] = "ipad"
        last: dict = {}
        for attempt in range(max(1, retries)):
            last = self._post("login/getLoginQrCode", body)
            if last.get("ret") == 200:
                return last
            if attempt + 1 < retries:
                import time

                time.sleep(retry_sleep_s)
        return last

    def check_login(self, app_id: str, uuid: str = "") -> dict:
        body: dict[str, Any] = {"appId": app_id}
        if uuid:
            body["uuid"] = uuid
        return self._post("login/checkLogin", body)

    def set_callback(self, callback_url: str) -> dict:
        if not self.token:
            raise RuntimeError("gewechat token required")
        path = "login/setCallback" if self.cloud else "tools/setCallback"
        return self._post(
            path,
            {"token": self.token, "callbackUrl": callback_url},
        )

    def post_text(self, app_id: str, wxid: str, text: str) -> dict:
        return self._post(
            "message/postText",
            {"appId": app_id, "toWxid": wxid, "content": text},
        )


def from_env() -> GewechatClient:
    base = os.environ.get("GEWECHAT_BASE_URL", "http://127.0.0.1:2531/v2/api")
    token = os.environ.get("GEWECHAT_TOKEN", "")
    return GewechatClient(base, token)
