"""SCNet cookie state loading with safe redaction."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_COOKIE_PATH = "/opt/lima-router/reverse_gateway_state/scnet_cookies.json"
PUBLIC_COOKIE_NAMES = {"language", "org.springframework.web.servlet.i18n.cookielocaleresolver.locale"}
REDACTED = "<redacted>"


@dataclass(frozen=True)
class CookieState:
    cookies: tuple[dict[str, Any], ...]

    def cookie_header(self) -> str:
        pairs = []
        for cookie in self.cookies:
            name = str(cookie.get("name") or "").strip()
            value = str(cookie.get("value") or "")
            if name:
                pairs.append(f"{name}={value}")
        return "; ".join(pairs)

    def redacted(self) -> list[dict[str, Any]]:
        redacted_cookies = []
        for cookie in self.cookies:
            item = dict(cookie)
            name = str(item.get("name") or "").lower()
            if name not in PUBLIC_COOKIE_NAMES:
                item["value"] = REDACTED
            redacted_cookies.append(item)
        return redacted_cookies


def cookie_path() -> Path:
    return Path(os.environ.get("SCNET_REVERSE_COOKIE_PATH", DEFAULT_COOKIE_PATH))


def load_cookie_state(path: Path | None = None) -> CookieState | None:
    selected = path or cookie_path()
    if not selected.is_file():
        return None
    raw = json.loads(selected.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("SCNet cookie export must be a list")
    cookies = tuple(cookie for cookie in raw if isinstance(cookie, dict) and cookie.get("name"))
    return CookieState(cookies=cookies)


def write_cookie_state(raw: list[dict[str, Any]], path: Path) -> CookieState:
    state = CookieState(cookies=tuple(raw))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state
