"""Guest/owner channel tools — wiki, weather, search, news, URL read, etc."""

from __future__ import annotations

import os
import re
from typing import Callable, Optional

from channel_gateway.public_apis import (
    fetch_calc,
    fetch_duckduckgo_instant,
    fetch_earthquake,
    fetch_exchange,
    fetch_holiday,
    fetch_ip_info,
    fetch_stock,
    fetch_time,
    fetch_translate,
    fetch_weather,
    fetch_wiki,
)
from channel_gateway.store import ChannelStore
from channel_gateway.tool_usage import (
    quota_exceeded_message,
    tool_limit,
    tools_enabled,
    utc_day,
)

CHANNEL_TOOL_INTENTS = frozenset({
    "menu",
    "wiki",
    "weather",
    "search",
    "read_url",
    "news",
    "translate",
    "exchange",
    "time",
    "hot",
    "ip",
    "calc",
    "holiday",
    "stock",
    "earthquake",
})

_TOOLS_MENU = (
    "LiMa 频道工具（需 LIMA_CHANNEL_TOOLS=1）\n"
    "/百科 <词> — 维基摘要\n"
    "/天气 <城市>\n"
    "/搜 <关键词> — 联网搜索\n"
    "/新闻 <关键词> — 新闻摘要\n"
    "/翻译 <文本>\n"
    "/汇率 <源> <目标> [金额]\n"
    "/时间 [时区]\n"
    "/热搜 [平台] — 微博/百度等热点\n"
    "/ip <地址>\n"
    "/算 <表达式> — 安全计算器\n"
    "/黄历 [日期] — 节假日/调休\n"
    "/股票 <代码> — 行情摘要\n"
    "/地震 — 近24h 全球地震简报\n"
    "/读 <https://...> — 安全抓取公开网页\n"
    "配额：访客每日有限次，主人更高；发送 /help 查看基础命令"
)


def tools_help_suffix() -> str:
    if not tools_enabled():
        return ""
    return (
        "\n--- 联网工具（LIMA_CHANNEL_TOOLS=1）---\n"
        "/menu — 工具菜单\n"
        "/百科 /天气 /搜 /新闻 /翻译 /汇率 /时间 /热搜 /ip\n"
        "/算 /黄历 /股票 /地震 /读"
    )


def _search_adapter():
    if not os.environ.get("TINYFISH_API_KEY", "").strip():
        return None
    from search_gateway.dev_adapter import get_dev_search_adapter

    return get_dev_search_adapter()


def _format_search_results(results: list[dict], *, max_items: int = 5) -> str:
    lines = []
    for idx, item in enumerate(results[:max_items], 1):
        title = str(item.get("title") or "无标题")[:80]
        url = str(item.get("url") or "")[:200]
        snippet = str(item.get("snippet") or item.get("text") or "")[:280]
        lines.append(f"{idx}. {title}\n{snippet}\n{url}")
    return "\n\n".join(lines) if lines else "无结果"


def _run_search(query: str) -> dict:
    adapter = _search_adapter()
    if adapter is not None:
        from search_gateway.dev_tools import search_docs

        raw = search_docs(query, adapter=adapter, max_results=5)
        if raw.get("ok"):
            text = _format_search_results(raw.get("results", []))
            return {"ok": True, "text": text or "无结果"}
        return {"ok": False, "error": raw.get("error", "search_failed")}
    return fetch_duckduckgo_instant(query)


def _run_read_url(url: str) -> dict:
    target = url.strip().split()[0][:500]
    if not target.startswith(("http://", "https://")):
        return {"ok": False, "error": "用法：/读 https://example.com"}
    adapter = _search_adapter()
    if adapter is not None:
        from search_gateway.dev_tools import read_url

        raw = read_url(target, adapter=adapter, max_chars=3500)
        if not raw.get("ok"):
            return {"ok": False, "error": raw.get("error", "fetch_failed")}
        title = raw.get("title") or ""
        body = (raw.get("text") or "")[:3500]
        return {"ok": True, "text": f"{title}\n{body}".strip()}
    return _simple_read_url(target)


def _simple_read_url(url: str, *, max_chars: int = 3500) -> dict:
    import urllib.request

    from search_gateway.safety import is_public_http_url

    if not is_public_http_url(url):
        return {"ok": False, "error": "url_blocked"}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LiMa-ChannelTools/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read(200_000).decode("utf-8", errors="replace")
        text = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()[:max_chars]
        if not text:
            return {"ok": False, "error": "页面无文本摘要"}
        return {"ok": True, "text": text}
    except Exception as exc:
        return {"ok": False, "error": f"抓取失败：{type(exc).__name__}"}


def _parse_exchange_args(args: str) -> tuple[str, str, float]:
    parts = args.split()
    if len(parts) < 2:
        return "", "", 1.0
    amount = 1.0
    if len(parts) >= 3:
        try:
            amount = float(parts[2])
        except ValueError:
            amount = 1.0
    return parts[0], parts[1], amount


class ChannelToolRunner:
    """Runs a tool intent with quota checks."""

    def __init__(self, store: ChannelStore):
        self._store = store

    def run(
        self,
        intent: str,
        args: str,
        *,
        user_hash: str,
        role: str,
    ) -> str:
        if intent == "menu":
            return _TOOLS_MENU

        tool_key = intent
        if intent == "news":
            tool_key = "news"
        limit = tool_limit(tool_key, role)
        if limit <= 0:
            return "该工具不可用"

        if intent != "menu":
            allowed, _ = self._store.consume_tool_quota(
                user_hash, tool_key, limit, day=utc_day()
            )
            if not allowed:
                return quota_exceeded_message(tool_key, limit)

        handlers: dict[str, Callable[[], dict]] = {
            "wiki": lambda: fetch_wiki(args),
            "weather": lambda: fetch_weather(args),
            "search": lambda: _run_search(args),
            "read_url": lambda: _run_read_url(args),
            "news": lambda: _run_search(f"新闻 {args}".strip() or "今日要闻"),
            "translate": lambda: fetch_translate(args),
            "exchange": lambda: fetch_exchange(*_parse_exchange_args(args)),
            "time": lambda: fetch_time(args.strip() or "Asia/Shanghai"),
            "hot": lambda: _run_search(f"{args or '微博'} 热搜 今日"),
            "ip": lambda: fetch_ip_info(args),
            "calc": lambda: fetch_calc(args),
            "holiday": lambda: fetch_holiday(args),
            "stock": lambda: fetch_stock(args),
            "earthquake": lambda: fetch_earthquake(),
        }
        handler = handlers.get(intent)
        if handler is None:
            return "未知工具"
        result = handler()
        if result.get("ok"):
            return str(result.get("text", ""))[:4000]
        return str(result.get("error", "工具执行失败"))[:500]


def run_channel_tool(
    store: ChannelStore,
    intent: str,
    args: str,
    *,
    channel_user_id_raw: str,
    role: str,
) -> str:
    if not tools_enabled():
        return "频道工具未开启。运维设置 LIMA_CHANNEL_TOOLS=1 后可用。"
    user_hash = store._hash_id(channel_user_id_raw)
    return ChannelToolRunner(store).run(
        intent, args, user_hash=user_hash, role=role
    )
