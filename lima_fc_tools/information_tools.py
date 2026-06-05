"""Telegram Function Calling tools."""

import logging
import os

from .http_client import _get
from .registry import tool

_log = logging.getLogger(__name__)


@tool(
    "get_weather",
    "Get current weather for a city.",
    {"properties": {"city": {"description": "City name.", "type": "string"}}, "required": ["city"], "type": "object"},
)
async def _weather(city: str) -> dict:
    r = await _get(f"https://wttr.in/{city}?format=j1", timeout=8)
    if isinstance(r, dict) and "current_condition" in r:
        cc = r["current_condition"][0]
        return {
            "city": city,
            "temp_c": cc.get("temp_C"),
            "feels_like_c": cc.get("FeelsLikeC"),
            "humidity": cc.get("humidity") + "%",
            "weather": cc.get("lang_zh", [{}])[0].get("value", cc.get("weatherDesc", [{}])[0].get("value", "")),
            "wind_kmph": cc.get("windspeedKmph"),
            "wind_dir": cc.get("winddir16Point"),
            "visibility_km": cc.get("visibility"),
            "uv_index": cc.get("uvIndex"),
        }
    return {"error": "unavailable", "raw": str(r)[:200]}


@tool(
    "get_air_quality",
    "Run the get_air_quality utility.",
    {"properties": {"city": {"description": "City name.", "type": "string"}}, "required": ["city"], "type": "object"},
)
async def _air_quality(city: str) -> dict:
    r = await _get(f"https://wttr.in/{city}?format=j1", timeout=8)
    if isinstance(r, dict) and "current_condition" in r:
        cc = r["current_condition"][0]
        return {
            "city": city,
            "humidity": cc.get("humidity"),
            "visibility_km": cc.get("visibility"),
            "uv_index": cc.get("uvIndex"),
            "cloud_cover": cc.get("cloudcover"),
        }
    return {"error": "unavailable"}


@tool(
    "get_ip_info",
    "Run the get_ip_info utility.",
    {
        "properties": {"ip": {"description": "Public IP address.", "type": "string"}},
        "required": ["ip"],
        "type": "object",
    },
)
async def _ip_info(ip: str) -> dict:
    r = await _get(f"http://ip-api.com/json/{ip}", {"lang": "zh-CN"})
    return r


@tool(
    "get_exchange_rate",
    "Run the get_exchange_rate utility.",
    {
        "properties": {
            "amount": {"default": 1, "description": "Amount to convert.", "type": "number"},
            "from_currency": {"description": "Source currency code.", "type": "string"},
            "to_currency": {"description": "Target currency code.", "type": "string"},
        },
        "required": ["from_currency", "to_currency"],
        "type": "object",
    },
)
async def _exchange_rate(from_currency: str, to_currency: str, amount: float = 1) -> dict:
    r = await _get(f"https://api.exchangerate-api.com/v4/latest/{from_currency.upper()}")
    rate = r.get("rates", {}).get(to_currency.upper(), 0)
    return {"from": from_currency, "to": to_currency, "rate": rate, "amount": amount, "result": round(amount * rate, 2)}


@tool(
    "get_holiday",
    "Run the get_holiday utility.",
    {
        "properties": {"date": {"description": "Date in YYYY-MM-DD format.", "type": "string"}},
        "required": ["date"],
        "type": "object",
    },
)
async def _holiday(date: str) -> dict:
    r = await _get("https://timor.tech/api/holiday/info/" + date)
    return r


@tool(
    "get_hot_search",
    "Run the get_hot_search utility.",
    {
        "properties": {
            "platform": {
                "description": "Source platform.",
                "enum": ["weibo", "baidu", "zhihu", "douyin", "toutiao", "bili"],
                "type": "string",
            }
        },
        "required": ["platform"],
        "type": "object",
    },
)
async def _hot_search(platform: str) -> dict:
    urls = {
        "weibo": "https://weibo.com/ajax/side/hotSearch",
        "baidu": "https://top.baidu.com/api/board?platform=wise&tab=realtime",
        "zhihu": "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=10",
        "douyin": "https://www.douyin.com/aweme/v1/web/hot/search/list/",
        "toutiao": "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
        "bili": "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all",
    }
    try:
        r = await _get(urls.get(platform, urls["baidu"]), timeout=8)
        return r if isinstance(r, dict) else {"data": str(r)[:500]}
    except Exception as exc:
        _log.warning("%s hot search failed: %s", platform, exc)
        return {"error": f"{platform} hot search unavailable"}


@tool(
    "get_news",
    "Fetch GNews headlines or keyword search results.",
    {
        "properties": {
            "category": {
                "default": "general",
                "description": "News category.",
                "enum": ["general", "world", "business", "technology", "entertainment", "sports", "science", "health"],
                "type": "string",
            },
            "keyword": {"default": "", "description": "Optional search keyword.", "type": "string"},
            "lang": {"default": "zh", "description": "Language code.", "type": "string"},
        },
        "required": [],
        "type": "object",
    },
)
async def _news(keyword: str = "", category: str = "general", lang: str = "zh") -> dict:
    key = os.environ.get("GNEWS_API_KEY", "")
    if not key:
        return {"error": "missing_gnews_api_key"}
    if keyword:
        r = await _get("https://gnews.io/api/v4/search", {"q": keyword, "lang": lang, "max": 5, "apikey": key})
    else:
        r = await _get(
            "https://gnews.io/api/v4/top-headlines", {"category": category, "lang": lang, "max": 5, "apikey": key}
        )
    articles = r.get("articles", []) if isinstance(r, dict) else []
    return {
        "articles": [
            {
                "title": a.get("title"),
                "description": a.get("description", "")[:100],
                "source": a.get("source", {}).get("name", ""),
            }
            for a in articles[:5]
        ]
    }


@tool(
    "translate_text",
    "Translate text to a target language.",
    {
        "properties": {
            "text": {"description": "Input text.", "type": "string"},
            "to": {"default": "zh", "description": "Target language code.", "type": "string"},
        },
        "required": ["text"],
        "type": "object",
    },
)
async def _translate(text: str, to: str = "zh") -> dict:
    r = await _get("https://api.mymemory.translated.net/get", {"q": text, "langpair": f"auto|{to}"})
    match = r.get("responseData", {})
    return {"translation": match.get("translatedText", ""), "source_lang": match.get("detectedLanguage", "")}


@tool("get_gold_price", "Run the get_gold_price utility.", {"properties": {}, "required": [], "type": "object"})
async def _gold_price() -> dict:
    try:
        r = await _get("https://hq.sinajs.cn/list=hf_GC", timeout=6)
        if isinstance(r, str) and "," in r:
            parts = r.split(",")
            return {"gold_usd_oz": parts[0].split("=")[-1].strip('"'), "raw": ",".join(parts[:6])}
    except Exception as exc:
        _log.warning("gold price fetch failed: %s", exc)
    r2 = await _get("https://api.exchangerate-api.com/v4/latest/USD")
    return {"note": "Gold price via exchange rate proxy", "usd_cny": r2.get("rates", {}).get("CNY", "N/A")}


@tool(
    "get_oil_price",
    "Run the get_oil_price utility.",
    {
        "properties": {"province": {"default": "Guangdong", "description": "Province name.", "type": "string"}},
        "required": [],
        "type": "object",
    },
)
async def _oil_price(province: str = "unavailable") -> dict:
    return {"note": "unavailable", "province": province, "reference": "unavailable"}


@tool(
    "get_express_tracking",
    "Run the get_express_tracking utility.",
    {
        "properties": {"number": {"description": "Tracking number.", "type": "string"}},
        "required": ["number"],
        "type": "object",
    },
)
async def _express(number: str) -> dict:
    try:
        r = await _get("https://www.kuaidi100.com/autonumber/autoComNum", {"resultv2": "1", "text": number})
        if isinstance(r, dict) and r.get("auto"):
            return {"number": number, "company": r["auto"][0].get("comCode", ""), "name": r["auto"][0].get("name", "")}
    except Exception as exc:
        _log.warning("express tracking failed for %s: %s", number, exc)
    return {"number": number, "note": "unavailable"}


@tool(
    "get_phone_info",
    "Run the get_phone_info utility.",
    {
        "properties": {"phone": {"description": "Phone number.", "type": "string"}},
        "required": ["phone"],
        "type": "object",
    },
)
async def _phone_info(phone: str) -> dict:
    r = await _get("https://api.aa1.cn/api/api-phone/", {"phone": phone})
    return r


@tool(
    "get_history_today",
    "Run the get_history_today utility.",
    {
        "properties": {
            "day": {"description": "Day number.", "type": "integer"},
            "month": {"description": "Month number.", "type": "integer"},
        },
        "required": ["month", "day"],
        "type": "object",
    },
)
async def _history_today(month: int, day: int) -> dict:
    r = await _get("https://api.aa1.cn/api/api-history/", {"month": month, "day": day})
    return r


@tool(
    "get_idiom",
    "Run the get_idiom utility.",
    {
        "properties": {"word": {"description": "Word to look up.", "type": "string"}},
        "required": ["word"],
        "type": "object",
    },
)
async def _idiom(word: str) -> dict:
    r = await _get("https://api.aa1.cn/api/api-chengyu/", {"word": word})
    return r


@tool(
    "generate_qrcode",
    "Run the generate_qrcode utility.",
    {"properties": {"text": {"description": "Input text.", "type": "string"}}, "required": ["text"], "type": "object"},
)
async def _qrcode(text: str) -> dict:
    url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={text}"
    return {"qrcode_url": url, "content": text}


@tool(
    "shorten_url",
    "Run the shorten_url utility.",
    {"properties": {"url": {"description": "URL.", "type": "string"}}, "required": ["url"], "type": "object"},
)
async def _shorten_url(url: str) -> dict:
    r = await _get("https://is.gd/create.php", {"format": "json", "url": url})
    return r
