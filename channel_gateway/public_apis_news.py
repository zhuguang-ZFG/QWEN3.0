"""60s hot-list and daily news briefing tools (split from public_apis.py)."""

from __future__ import annotations

import json
import logging
import urllib.error

from channel_gateway.public_apis import _get_json

_log = logging.getLogger(__name__)

_HOT_PLATFORM_MAP = {
    "微博": "weibo",
    "weibo": "weibo",
    "百度": "baidu",
    "baidu": "baidu",
    "知乎": "zhihu",
    "zhihu": "zhihu",
    "bilibili": "bilibili",
    "b站": "bilibili",
    "抖音": "douyin",
    "douyin": "douyin",
}


def _normalize_hot_items(payload: dict, *, max_items: int = 15) -> list[str]:
    rows = payload.get("data")
    if isinstance(rows, dict):
        rows = rows.get("list") or rows.get("data") or []
    if not isinstance(rows, list):
        return []
    lines: list[str] = []
    for idx, item in enumerate(rows[:max_items], 1):
        if isinstance(item, str):
            lines.append(f"{idx}. {item[:120]}")
            continue
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        hot = item.get("hot") or item.get("hotValue") or item.get("index")
        if not title:
            continue
        suffix = f" ({hot})" if hot not in (None, "") else ""
        lines.append(f"{idx}. {title[:100]}{suffix}")
    return lines


def fetch_hot_60s(platform: str = "微博") -> dict:
    """Hot list via free 60s/vvhan-style API (radar paragraph XIII)."""
    key = platform.strip() or "微博"
    type_key = _HOT_PLATFORM_MAP.get(key.lower(), _HOT_PLATFORM_MAP.get(key, "weibo"))
    urls = (
        f"https://60s.viki.moe/v2/{type_key}",
        f"https://api.vvhan.com/api/hotlist?type={type_key}",
        f"https://api.vvhan.com/api/hotlist/{type_key}",
    )
    last_error = "hot list unavailable"
    for url in urls:
        try:
            data = _get_json(url)
            lines = _normalize_hot_items(data)
            if lines:
                return {"ok": True, "text": f"[{key} Hot]\n" + "\n".join(lines)}
            last_error = "hot list empty"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = f"hot list failed: {type(exc).__name__}"
            _log.debug("fetch_hot_60s url=%s err=%s", url, type(exc).__name__)
    return {"ok": False, "error": last_error}


def _extract_60s_news(data: object) -> tuple[str, list[str]]:
    """Normalize 60s news payloads (vvhan / viki v2 / static CDN)."""
    if not isinstance(data, dict):
        return "", []
    payload = data
    if isinstance(payload.get("data"), dict) and (
        "news" in payload["data"] or payload.get("code") == 200
    ):
        inner = payload["data"]
        if isinstance(inner, dict) and "news" in inner:
            payload = inner
        elif payload.get("code") == 200 and isinstance(inner, dict):
            payload = inner
    block = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if isinstance(block, list):
        date_str = str(payload.get("date") or "").strip()
        news = block
    elif isinstance(block, dict):
        date_str = str(block.get("date") or block.get("time") or "").strip()
        news = block.get("news") or block.get("data") or []
    else:
        return "", []
    if not isinstance(news, list):
        news = []
    lines = [str(item).strip() for item in news if str(item).strip()]
    return date_str, lines


def _news_60s_urls() -> tuple[str, ...]:
    from datetime import date

    today = date.today().isoformat()
    return (
        "https://60s.viki.moe/v2/60s",
        f"https://60s-static.viki.moe/60s/{today}.json",
        f"https://cdn.jsdelivr.net/gh/vikiboss/60s-static-host@main/static/60s/{today}.json",
        "https://api.vvhan.com/api/60s?type=json",
        "https://api.vvhan.com/api/60s",
    )


def fetch_news_60s() -> dict:
    """Daily 60-second world briefing (radar paragraph XIII)."""
    last_error = "60s news unavailable"
    for url in _news_60s_urls():
        try:
            data = _get_json(url)
            date_str, lines = _extract_60s_news(data)
            if lines:
                head = f"[60s News {date_str}]".strip()
                body = "\n".join(f"  {line[:200]}" for line in lines[:20])
                return {"ok": True, "text": f"{head}\n{body}"[:1500]}
            last_error = "60s news empty"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = f"60s news failed: {type(exc).__name__}"
            _log.debug("fetch_news_60s url=%s err=%s", url, type(exc).__name__)
    return {"ok": False, "error": last_error}
