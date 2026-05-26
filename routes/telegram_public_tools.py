"""Telegram public tool commands — channel §十三 parity (no API keys)."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

import telegram_bot
from routes.telegram_commands import _operator_error

_log = logging.getLogger(__name__)

_TOOLS_HELP = (
    "LiMa 实用工具（与频道 /menu 同源）\n"
    "/news — 60秒读懂世界\n"
    "/news <词> — 新闻搜索\n"
    "/hot [平台] — 热搜（微博/百度/B站…）\n"
    "/weather <城市> — 天气\n"
    "/wiki <词条> — 维基摘要\n"
    "/exchange <源> <目标> [金额] — 汇率\n"
    "/calc <表达式> — 计算器\n"
    "/time [时区] — 当前时间\n"
    "/translate <文本> — 翻译\n"
    "/stock <代码> — 行情\n"
    "/holiday [日期] — 节假日/调休\n"
    "/ip <地址> — IP 归属\n"
    "/earthquake — 近24h 地震简报\n"
    "/dict <英文> — 词典\n"
    "/whois <域名>\n"
    "/qr <文本或URL> — 二维码链接\n"
    "/geocode <地点> — 地理编码\n"
    "/random [seed] — 假用户数据\n"
    "/ssl <域名> — TLS 证书\n"
    "/regex <pattern> <text> — 正则测试\n"
    "/image [关键词] — 占位图\n"
    "/uuid [1-5] — 生成 UUID4\n"
    "/tools — 本菜单"
)


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


def _run_tool(tool: str, args: str) -> dict:
    from channel_gateway.public_apis import (
        fetch_calc,
        fetch_earthquake,
        fetch_exchange,
        fetch_holiday,
        fetch_hot_60s,
        fetch_ip_info,
        fetch_news_60s,
        fetch_stock,
        fetch_time,
        fetch_translate,
        fetch_weather,
        fetch_wiki,
    )

    from channel_gateway.public_apis_lookup import (
        fetch_dictionary,
        fetch_geocode,
        fetch_image,
        fetch_qr,
        fetch_randomuser,
        fetch_regex_test,
        fetch_ssl,
        fetch_uuid,
        fetch_whois,
    )

    handlers: dict[str, Callable[[], dict]] = {
        "weather": lambda: fetch_weather(args),
        "wiki": lambda: fetch_wiki(args),
        "exchange": lambda: fetch_exchange(*_parse_exchange_args(args)),
        "calc": lambda: fetch_calc(args),
        "time": lambda: fetch_time(args.strip() or "Asia/Shanghai"),
        "translate": lambda: fetch_translate(args),
        "stock": lambda: fetch_stock(args),
        "holiday": lambda: fetch_holiday(args),
        "ip": lambda: fetch_ip_info(args),
        "earthquake": lambda: fetch_earthquake(),
        "hot": lambda: fetch_hot_60s(args or "微博"),
        "news": lambda: fetch_news_60s(),
        "dict": lambda: fetch_dictionary(args),
        "whois": lambda: fetch_whois(args),
        "qr": lambda: fetch_qr(args),
        "geocode": lambda: fetch_geocode(args),
        "randomuser": lambda: fetch_randomuser(args),
        "ssl": lambda: fetch_ssl(args),
        "regex": lambda: fetch_regex_test(args),
        "image": lambda: fetch_image(args),
        "uuid": lambda: fetch_uuid(args),
    }
    handler = handlers.get(tool)
    if handler is None:
        return {"ok": False, "error": "未知工具"}
    return handler()


async def _send_tool_result(chat_id: str, result: dict, *, tool: str) -> None:
    if result.get("ok"):
        await telegram_bot.send_message(
            str(result.get("text", ""))[:4000],
            chat_id=chat_id,
            parse_mode="",
        )
        return
    await telegram_bot.send_message(
        str(result.get("error", "工具暂不可用"))[:500],
        chat_id=chat_id,
        parse_mode="",
    )


async def cmd_tools(chat_id: str) -> None:
    await telegram_bot.send_message(_TOOLS_HELP, chat_id=chat_id, parse_mode="")


async def cmd_public_tool(chat_id: str, tool: str, args: str) -> None:
    try:
        result = await asyncio.to_thread(_run_tool, tool, args)
        await _send_tool_result(chat_id, result, tool=tool)
    except Exception:
        _log.exception("cmd_public_tool failed tool=%s", tool)
        await telegram_bot.send_message(_operator_error(tool), chat_id=chat_id)


async def cmd_news(chat_id: str, args: str) -> None:
    query = args.strip()
    try:
        if query:
            from routes.telegram_commands import cmd_chat

            await cmd_chat(chat_id, f"搜索今日新闻：{query}")
            return
        result = await asyncio.to_thread(_run_tool, "news", "")
        await _send_tool_result(chat_id, result, tool="news")
    except Exception:
        _log.exception("cmd_news failed")
        await telegram_bot.send_message(_operator_error("news"), chat_id=chat_id)


async def cmd_hot(chat_id: str, args: str) -> None:
    await cmd_public_tool(chat_id, "hot", args)
