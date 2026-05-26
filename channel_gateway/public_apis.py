"""Sync public HTTP helpers for WeChat channel tools (no API keys required)."""

from __future__ import annotations

import ast
import json
import logging
import operator
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_log = logging.getLogger(__name__)

_USER_AGENT = "LiMa-ChannelTools/1.0"
_TIMEOUT = 10


def _get_json(url: str, *, headers: dict | None = None) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace").strip()


def fetch_weather(city: str) -> dict:
    safe = re.sub(r"[^\w\u4e00-\u9fff\s\-]", "", city.strip())[:40]
    if not safe:
        return {"ok": False, "error": "请提供城市名，例如：/天气 北京"}
    try:
        enc = urllib.parse.quote(safe)
        line = _get_text(f"https://wttr.in/{enc}?format=3&lang=zh")
        return {"ok": True, "text": f"{safe}：{line}"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"天气服务暂不可用：{type(exc).__name__}"}


def fetch_wiki(query: str, *, lang: str = "zh") -> dict:
    q = query.strip()[:120]
    if not q:
        return {"ok": False, "error": "请提供词条，例如：/百科 Python"}
    wiki_lang = "zh" if lang.startswith("zh") else "en"
    base = f"https://{wiki_lang}.wikipedia.org/w/api.php"
    try:
        search_url = (
            f"{base}?action=query&list=search&srsearch={urllib.parse.quote(q)}"
            f"&format=json&utf8=1&srlimit=1"
        )
        data = _get_json(search_url)
        hits = data.get("query", {}).get("search", [])
        if not hits:
            return {"ok": False, "error": f"未找到与「{q}」相关的百科条目"}
        title = hits[0]["title"]
        extract_url = (
            f"{base}?action=query&prop=extracts&exintro=1&explaintext=1"
            f"&titles={urllib.parse.quote(title)}&format=json"
        )
        page = _get_json(extract_url)
        pages = page.get("query", {}).get("pages", {})
        page_id = next(iter(pages), None)
        if page_id is None:
            return {"ok": False, "error": "百科摘要获取失败"}
        extract = (pages[page_id].get("extract") or "")[:1200]
        return {"ok": True, "text": f"【{title}】\n{extract}"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
        return {"ok": False, "error": f"百科服务暂不可用：{type(exc).__name__}"}


def fetch_exchange(from_ccy: str, to_ccy: str, amount: float = 1.0) -> dict:
    src = from_ccy.strip().upper()[:6]
    dst = to_ccy.strip().upper()[:6]
    if not src or not dst:
        return {"ok": False, "error": "用法：/汇率 USD CNY 100"}
    try:
        data = _get_json(f"https://api.frankfurter.app/latest?from={src}&to={dst}")
        rate = float(data.get("rates", {}).get(dst, 0))
        if rate <= 0:
            return {"ok": False, "error": "无法获取汇率"}
        result = round(amount * rate, 4)
        return {
            "ok": True,
            "text": f"{amount} {src} ≈ {result} {dst}（汇率 {rate}，日期 {data.get('date', '')}）",
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "error": f"汇率服务暂不可用：{type(exc).__name__}"}


def fetch_time(tz_name: str = "Asia/Shanghai") -> dict:
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        _log.debug("invalid timezone %s, fallback Asia/Shanghai: %s", tz_name, type(exc).__name__)
        tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(timezone.utc).astimezone(tz)
    return {
        "ok": True,
        "text": now.strftime(f"%Y-%m-%d %H:%M:%S %Z（{tz_name}）"),
    }


def fetch_translate(text: str, *, target: str = "zh-CN") -> dict:
    raw = text.strip()[:500]
    if not raw:
        return {"ok": False, "error": "用法：/翻译 hello"}
    translated = translate_text_only(raw, target=target)
    if not translated:
        return {"ok": False, "error": "翻译失败"}
    return {"ok": True, "text": f"{raw}\n→ {translated}"}


def translate_text_only(text: str, *, target: str = "zh-CN", max_len: int = 500) -> str | None:
    """Return translated text only (MyMemory, no API key)."""
    raw = text.strip()[:max_len]
    if not raw:
        return None
    pair = f"en|{target}" if target.startswith("zh") else f"auto|{target}"
    try:
        url = (
            "https://api.mymemory.translated.net/get?"
            + urllib.parse.urlencode({"q": raw, "langpair": pair})
        )
        data = _get_json(url)
        translated = str(data.get("responseData", {}).get("translatedText") or "").strip()
        return translated or None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        _log.debug("translate_text_only failed: %s", type(exc).__name__)
        return None


def fetch_ip_info(ip: str) -> dict:
    addr = ip.strip()[:45]
    if not addr:
        return {"ok": False, "error": "用法：/ip 8.8.8.8"}
    if not re.match(r"^[\d.a-fA-F:]+$", addr):
        return {"ok": False, "error": "IP 格式无效"}
    try:
        data = _get_json(f"http://ip-api.com/json/{urllib.parse.quote(addr)}?lang=zh-CN")
        if data.get("status") != "success":
            return {"ok": False, "error": data.get("message", "查询失败")}
        return {
            "ok": True,
            "text": (
                f"{addr}\n"
                f"国家/地区：{data.get('country', '')} {data.get('regionName', '')} "
                f"{data.get('city', '')}\n"
                f"运营商：{data.get('isp', '')}\n"
                f"时区：{data.get('timezone', '')}"
            ),
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"IP 查询暂不可用：{type(exc).__name__}"}


def fetch_duckduckgo_instant(query: str, *, max_snippets: int = 3) -> dict:
    q = query.strip()[:200]
    if not q:
        return {"ok": False, "error": "请提供搜索词"}
    try:
        url = (
            "https://api.duckduckgo.com/?"
            + urllib.parse.urlencode({"q": q, "format": "json", "no_redirect": 1})
        )
        data = _get_json(url)
        lines: list[str] = []
        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            lines.append(abstract[:800])
            src = data.get("AbstractURL") or ""
            if src:
                lines.append(f"来源：{src}")
        for topic in (data.get("RelatedTopics") or [])[:max_snippets]:
            if isinstance(topic, dict) and topic.get("Text"):
                lines.append(topic["Text"][:300])
            elif isinstance(topic, dict) and topic.get("Topics"):
                for sub in topic["Topics"][:2]:
                    if sub.get("Text"):
                        lines.append(sub["Text"][:300])
        if not lines:
            return {"ok": False, "error": "未找到摘要，可换关键词或使用 /搜"}
        return {"ok": True, "text": "\n\n".join(lines)[:1500]}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"搜索暂不可用：{type(exc).__name__}"}


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        val = _safe_eval(node.operand)
        return val if isinstance(node.op, ast.UAdd) else -val
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return float(_BIN_OPS[type(node.op)](left, right))
    raise ValueError("unsupported expression")


def fetch_calc(expr: str) -> dict:
    raw = expr.strip()[:200]
    if not raw:
        return {"ok": False, "error": "用法：/算 1+2*3"}
    if not re.match(r"^[\d\s+\-*/%.()]+$", raw):
        return {"ok": False, "error": "仅支持数字与 + - * / % ( ) 运算"}
    try:
        tree = ast.parse(raw, mode="eval")
        value = _safe_eval(tree)
        return {"ok": True, "text": f"{raw} = {value:g}"}
    except (SyntaxError, ValueError, ZeroDivisionError) as exc:
        return {"ok": False, "error": f"无法计算：{exc}"}


def fetch_holiday(date_str: str) -> dict:
    raw = date_str.strip() or datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return {"ok": False, "error": "用法：/黄历 2026-05-25（可省略日期）"}
    try:
        data = _get_json(f"https://timor.tech/api/holiday/info/{raw}")
        holiday = data.get("holiday") or {}
        name = holiday.get("name") or data.get("type", {}).get("name", "")
        wage = holiday.get("wage", "")
        extra = "（调休/节假日）" if holiday else "（工作日）"
        detail = f"{raw} {name}{extra}"
        if wage:
            detail += f"，薪资倍数：{wage}"
        return {"ok": True, "text": detail}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"黄历服务暂不可用：{type(exc).__name__}"}


def fetch_stock(symbol: str) -> dict:
    sym = re.sub(r"[^\w.\-]", "", symbol.strip().upper())[:16]
    if not sym:
        return {"ok": False, "error": "用法：/股票 AAPL 或 /股票 600519.SS"}
    try:
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            + urllib.parse.quote(sym)
            + "?interval=1d&range=1d"
        )
        data = _get_json(url)
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        currency = meta.get("currency", "")
        name = meta.get("shortName") or sym
        if price is None:
            return {"ok": False, "error": f"未找到行情：{sym}"}
        return {
            "ok": True,
            "text": f"{name} ({sym})\n现价：{price} {currency}".strip(),
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, IndexError) as exc:
        return {"ok": False, "error": f"行情暂不可用：{type(exc).__name__}"}


def fetch_earthquake(limit: int = 5) -> dict:
    try:
        data = _get_json(
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
        )
        lines: list[str] = ["近24h 全球 M2.5+ 地震（USGS）："]
        for feat in (data.get("features") or [])[:limit]:
            props = feat.get("properties") or {}
            mag = props.get("mag", "?")
            place = str(props.get("place", ""))[:80]
            lines.append(f"· M{mag} {place}")
        if len(lines) <= 1:
            return {"ok": False, "error": "暂无地震数据"}
        return {"ok": True, "text": "\n".join(lines)[:1500]}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"地震数据暂不可用：{type(exc).__name__}"}
