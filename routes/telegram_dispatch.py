"""Telegram slash-command dispatch (split from routes/telegram.py)."""

from __future__ import annotations

import logging
import telegram_bot

_log = logging.getLogger(__name__)
from routes.telegram_commands import (
    cmd_cache,
    cmd_chat,
    cmd_clear,
    cmd_code,
    cmd_device,
    cmd_eval,
    cmd_github,
    cmd_stop,
    cmd_task,
    cmd_tasks,
    cmd_top,
    cmd_uptime,
    cmd_voice,
    cmd_voicechat,
)
from routes.telegram_codesearch_tools import cmd_codesearch
from routes.telegram_diag_tools import cmd_oldllm
from routes.telegram_eval_tools import (
    cmd_archiveeval,
    cmd_evaldigest,
    cmd_evalreport,
    cmd_evalschedule,
    cmd_evalslice,
    cmd_evalstatus,
    cmd_poolgate,
)
from routes.telegram_public_tools import (
    cmd_hot,
    cmd_news,
    cmd_public_tool,
    cmd_tools,
)
from routes.telegram_quick_menu import cmd_help, cmd_menu, expand_command_alias

_PUBLIC_TOOL_COMMANDS: dict[str, str] = {
    "/weather": "weather",
    "/wiki": "wiki",
    "/exchange": "exchange",
    "/calc": "calc",
    "/time": "time",
    "/translate": "translate",
    "/stock": "stock",
    "/holiday": "holiday",
    "/ip": "ip",
    "/earthquake": "earthquake",
    "/dict": "dict",
    "/whois": "whois",
    "/qr": "qr",
    "/geocode": "geocode",
    "/random": "randomuser",
    "/ssl": "ssl",
    "/regex": "regex",
    "/image": "image",
    "/uuid": "uuid",
}


async def _dispatch_status_health_budget(
    chat_id: str, cmd: str, arg: str, *, status_fn, health_fn, budget_fn
) -> bool:
    if cmd == "/status":
        await status_fn(chat_id)
        return True
    if cmd == "/health":
        await health_fn(chat_id, arg.strip())
        return True
    if cmd == "/budget":
        await budget_fn(chat_id)
        return True
    return False


async def _dispatch_operator(chat_id: str, cmd: str, arg: str, *, logs_fn, restart_fn) -> bool:
    if cmd == "/logs":
        await logs_fn(chat_id, arg.strip())
        return True
    if cmd == "/restart":
        await restart_fn(chat_id)
        return True
    if cmd == "/eval":
        await cmd_eval(chat_id, arg.strip())
        return True
    if cmd == "/evalslice":
        await cmd_evalslice(chat_id, arg)
        return True
    if cmd == "/evalreport":
        await cmd_evalreport(chat_id, arg)
        return True
    if cmd == "/archiveeval":
        await cmd_archiveeval(chat_id, arg)
        return True
    if cmd == "/poolgate":
        await cmd_poolgate(chat_id, arg)
        return True
    if cmd == "/evalschedule":
        await cmd_evalschedule(chat_id, arg)
        return True
    if cmd == "/evalstatus":
        await cmd_evalstatus(chat_id, arg)
        return True
    if cmd == "/evaldigest":
        await cmd_evaldigest(chat_id, arg)
        return True
    if cmd == "/codesearch":
        await cmd_codesearch(chat_id, arg)
        return True
    if cmd == "/oldllm":
        await cmd_oldllm(chat_id, arg)
        return True
    if cmd == "/s3":
        from routes.telegram_tgs3_commands import cmd_s3_list, cmd_s3_put, cmd_s3_stats

        sub = arg.strip().split()[0] if arg.strip() else "list"
        if sub == "put":
            await cmd_s3_put(chat_id, arg)
        elif sub == "stats":
            await cmd_s3_stats(chat_id, arg)
        else:
            await cmd_s3_list(chat_id, arg)
        return True
    if cmd == "/ci":
        from routes.telegram_ci_tools import cmd_ci, cmd_ci_detail

        parts = arg.strip().split()
        if len(parts) >= 3:
            # /ci owner/repo branch run_id → detail mode
            try:
                int(parts[2])
                await cmd_ci_detail(chat_id, arg)
                return True
            except ValueError:
                pass
        await cmd_ci(chat_id, arg)
        return True
    if cmd in ("/kb", "/search"):
        from routes.telegram_knowledge import cmd_kb

        await cmd_kb(chat_id, arg)
        return True
    if cmd == "/save":
        from routes.telegram_knowledge import cmd_save

        await cmd_save(chat_id, arg)
        return True
    if cmd == "/memstats":
        from routes.telegram_knowledge import cmd_memstats

        await cmd_memstats(chat_id, arg)
        return True
    if cmd == "/feed":
        from routes.telegram_knowledge import cmd_feed

        await cmd_feed(chat_id, arg)
        return True
    if cmd == "/learn":
        from routes.telegram_knowledge import cmd_learn

        await cmd_learn(chat_id, arg)
        return True
    if cmd == "/outcome":
        from routes.telegram_knowledge import cmd_outcome

        await cmd_outcome(chat_id, arg)
        return True
    if cmd == "/digest":
        from routes.telegram_knowledge import cmd_digest

        await cmd_digest(chat_id, arg)
        return True
    if cmd == "/contracts":
        from routes.telegram_knowledge import cmd_contracts

        await cmd_contracts(chat_id, arg)
        return True
    if cmd == "/inbox":
        from routes.telegram_knowledge import cmd_inbox
        await cmd_inbox(chat_id, arg)
        return True
    if cmd == "/dashboard":
        from routes.telegram_knowledge import cmd_dashboard
        await cmd_dashboard(chat_id, arg)
        return True
    if cmd == "/investigate":
        from routes.telegram_dev_skills import cmd_investigate
        await cmd_investigate(chat_id, arg)
        return True
    if cmd == "/review":
        from routes.telegram_dev_skills import cmd_review
        await cmd_review(chat_id, arg)
        return True
    if cmd == "/ship":
        from routes.telegram_dev_skills import cmd_ship
        await cmd_ship(chat_id, arg)
        return True
    return False


def _record_command_outcome(cmd: str, chat_id: str, ok: bool) -> None:
    """Record a Telegram command to the Outcome Ledger (fire-and-forget)."""
    try:
        from session_memory.outcome_ledger import record

        record(
            source="telegram",
            event_type="command",
            outcome="success" if ok else "failure",
            task_id=chat_id,
            scenario="ops",
            summary=f"cmd={cmd} ok={ok}",
            tags=["telegram", cmd.lstrip("/"), "success" if ok else "failure"],
        )
    except Exception as exc:
        _log.debug("telegram cmd record skipped: %s", type(exc).__name__)  # never block main path


async def _dispatch_chat_session(chat_id: str, cmd: str, arg: str) -> bool:
    mapping = {
        "/chat": lambda: cmd_chat(chat_id, arg),
        "/clear": lambda: cmd_clear(chat_id),
        "/code": lambda: cmd_code(chat_id, arg),
        "/top": lambda: cmd_top(chat_id),
        "/uptime": lambda: cmd_uptime(chat_id),
        "/task": lambda: cmd_task(chat_id, arg),
        "/tasks": lambda: cmd_tasks(chat_id),
        "/stop": lambda: cmd_stop(chat_id, arg.strip()),
        "/cache": lambda: cmd_cache(chat_id),
        "/voice": lambda: cmd_voice(chat_id, arg),
        "/voicechat": lambda: cmd_voicechat(chat_id, arg),
        "/github": lambda: cmd_github(chat_id, arg),
        "/device": lambda: cmd_device(chat_id, arg),
        "/news": lambda: cmd_news(chat_id, arg),
        "/hot": lambda: cmd_hot(chat_id, arg),
        "/tools": lambda: cmd_tools(chat_id),
    }
    handler = mapping.get(cmd)
    if handler is None:
        return False
    await handler()
    return True


async def dispatch_command(
    chat_id: str,
    text: str,
    *,
    status_fn,
    health_fn,
    budget_fn,
    logs_fn,
    restart_fn,
) -> None:
    """Route a single slash command line to the appropriate handler."""
    text = expand_command_alias(text)
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]
    arg = parts[1] if len(parts) > 1 else ""
    ok = False

    try:
        if cmd in ("/help",):
            await cmd_help(chat_id)
            ok = True
            return
        if cmd in ("/menu",):
            await cmd_menu(chat_id, with_reply_keyboard=True)
            ok = True
            return

        pub = _PUBLIC_TOOL_COMMANDS.get(cmd)
        if pub is not None:
            await cmd_public_tool(chat_id, pub, arg)
            ok = True
            return

        if await _dispatch_status_health_budget(
            chat_id, cmd, arg, status_fn=status_fn, health_fn=health_fn, budget_fn=budget_fn
        ):
            ok = True
            return
        if await _dispatch_chat_session(chat_id, cmd, arg):
            ok = True
            return
        if await _dispatch_operator(
            chat_id, cmd, arg, logs_fn=logs_fn, restart_fn=restart_fn
        ):
            ok = True
            return

        if cmd == "/start":
            await telegram_bot.send_message(
                "LiMa Bot 就绪。\n"
                "发 /menu 或「菜单」打开快捷按钮；直接打字即可对话。\n"
                "发 /help 查看分类说明。",
                chat_id=chat_id,
                parse_mode="",
            )
            await cmd_menu(chat_id, with_reply_keyboard=True)
            ok = True
            return

        await telegram_bot.send_message("Unknown command", chat_id=chat_id)
    finally:
        _record_command_outcome(cmd, chat_id, ok)
        await cmd_menu(chat_id, with_reply_keyboard=True)
