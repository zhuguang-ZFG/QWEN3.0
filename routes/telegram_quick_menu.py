"""Telegram operator quick menu — buttons, aliases, and BotFather command list."""

from __future__ import annotations

from typing import Awaitable, Callable

import telegram_bot

DispatchFn = Callable[[str, str], Awaitable[None]]

# Short slash aliases → canonical command prefix (no args).
COMMAND_ALIASES: dict[str, str] = {
    "/h": "/help",
    "/m": "/menu",
    "/s": "/status",
    "/b": "/budget",
    "/t": "/top",
    "/n": "/news",
}

# Plain-text shortcuts (exact match, case-insensitive for ASCII).
TEXT_SHORTCUTS: dict[str, str] = {
    "菜单": "/menu",
    "帮助": "/help",
    "使用说明": "/help",
    "状态": "/status",
    "负载": "/top",
    "热搜": "/hot",
    "新闻": "/news",
    "工具": "/tools",
    "清空": "/clear",
    "设备": "/device status",
    "📋 菜单": "/menu",
    "📊 状态": "/status",
    "🔥 热搜": "/hot",
    "📰 新闻": "/news",
}

HELP_TEXT = """LiMa Operator 快捷指南

【Operator Console】
/status 后端健康 · /top 负载 · /budget 配额
/hot 热搜 · /news 新闻 · /tools 工具清单
/device status 设备状态 · /github owner/repo path

【Eval】
/evalslice [full] 运行评测 · /evalreport full 排名
/evalstatus 总览 · /evaldigest 摘要 · /poolgate 降级池

【Task】
/task id 查看任务 · /tasks 任务列表

【Storage】
/s3 list 文件清单 · /s3 stats 存储统计
/archiveeval full doc 归档评测

【别名】
/h=help /m=menu /s=status /b=budget /t=top /n=news
/evalslice [full] · /evalreport full · /poolgate · /evalschedule
/archiveeval full doc · /oldllm sync · /codesearch [query]

完整列表仍可用 /tools；重启等危险操作不在快捷菜单。"""

# Shown in Telegram "/" autocomplete (BotFather setMyCommands).
BOT_COMMANDS: list[dict[str, str]] = [
    {"command": "menu", "description": "快捷菜单（点按钮）"},
    {"command": "help", "description": "命令帮助"},
    {"command": "status", "description": "后端健康概览"},
    {"command": "hot", "description": "热搜榜"},
    {"command": "news", "description": "60秒读懂世界"},
    {"command": "tools", "description": "实用工具列表"},
    {"command": "evalreport", "description": "Eval 排名摘要"},
    {"command": "oldllm", "description": "TheOldLLM 诊断/sync"},
    {"command": "device", "description": "Device Gateway 状态"},
    {"command": "top", "description": "CPU/内存/连接"},
    {"command": "budget", "description": "配额用量"},
    {"command": "clear", "description": "清空对话历史"},
    {"command": "chat", "description": "带问题对话"},
]

# callback_data → (display hint, command line to dispatch)
QUICK_ACTIONS: dict[str, str] = {
    "status": "/status",
    "top": "/top",
    "budget": "/budget",
    "uptime": "/uptime",
    "hot": "/hot",
    "news": "/news",
    "tools": "/tools",
    "weather": "/weather 深圳",
    "wiki": "/wiki Python",
    "calc": "/calc 1+2",
    "evalreport": "/evalreport full",
    "poolgate": "/poolgate",
    "oldllm": "/oldllm sync",
    "archiveeval": "/archiveeval full doc",
    "evalschedule": "/evalschedule",
    "evalstatus": "/evalstatus",
    "evaldigest": "/evaldigest",
    "codesearch": "/codesearch",
    "device": "/device status",
    "clear": "/clear",
    "help": "/help",
    "menu": "/menu",
}


def expand_command_alias(text: str) -> str:
    """Expand /h → /help etc. on the first token."""
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return raw
    parts = raw.split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]
    mapped = COMMAND_ALIASES.get(cmd)
    if not mapped:
        return raw
    suffix = parts[1] if len(parts) > 1 else ""
    return f"{mapped} {suffix}".strip()


def resolve_text_shortcut(text: str) -> str | None:
    """Map 菜单/帮助等 plain text to a slash command."""
    key = (text or "").strip()
    if not key:
        return None
    if key in TEXT_SHORTCUTS:
        return TEXT_SHORTCUTS[key]
    lower = key.lower()
    return TEXT_SHORTCUTS.get(lower)


def _btn(label: str, action: str) -> dict:
    return {"text": label, "callback_data": f"qm:{action}"}


def main_menu_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [_btn("📊 状态", "status"), _btn("⚙️ 负载", "top"), _btn("💰 配额", "budget")],
            [_btn("🔥 热搜", "hot"), _btn("📰 新闻", "news"), _btn("🧰 工具", "tools")],
            [_btn("📈 Eval", "evalreport"), _btn("📋 总览", "evalstatus"), _btn("🚧 Pool", "poolgate")],
            [_btn("📊 摘要", "evaldigest"), _btn("🔄 OldLLM", "oldllm"), _btn("🔍 Code", "codesearch")],
            [_btn("📦 归档", "archiveeval"), _btn("📡 设备", "device"), _btn("🧹 清空", "clear")],
            [_btn("❓ 帮助", "help"), _btn("📋 菜单", "menu")],
        ]
    }


def reply_keyboard_markup() -> dict:
    return {
        "keyboard": [
            [{"text": "📋 菜单"}, {"text": "📊 状态"}],
            [{"text": "🔥 热搜"}, {"text": "📰 新闻"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


async def cmd_help(chat_id: str) -> None:
    await telegram_bot.send_message(HELP_TEXT, chat_id=chat_id, parse_mode="")


async def cmd_menu(chat_id: str, *, with_reply_keyboard: bool = False) -> None:
    payload: dict = {
        "chat_id": chat_id,
        "text": "LiMa 快捷菜单 — 点按钮执行；也可直接打字聊天。",
        "reply_markup": main_menu_keyboard(),
    }
    result = await telegram_bot._api_call("sendMessage", payload)
    if not result or not result.get("ok"):
        await telegram_bot.send_message(
            "LiMa 快捷菜单（发送失败，请试 /status）",
            chat_id=chat_id,
            parse_mode="",
        )
        return
    if with_reply_keyboard:
        await telegram_bot._api_call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "底部键盘已启用：菜单 / 状态 / 热搜 / 新闻",
                "reply_markup": reply_keyboard_markup(),
            },
        )


async def sync_bot_commands() -> bool:
    return await telegram_bot.set_my_commands(BOT_COMMANDS)


async def handle_quick_callback(
    chat_id: str,
    data: str,
    dispatch: DispatchFn,
) -> bool:
    """Handle qm:* inline button taps."""
    if not data.startswith("qm:"):
        return False
    action = data[3:].strip()
    command = QUICK_ACTIONS.get(action)
    if not command:
        return False
    await dispatch(chat_id, command)
    return True
