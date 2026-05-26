"""Extended Telegram command handlers and background tasks for LiMa."""

import asyncio
import importlib
import logging
import os
import random
import subprocess
import time
from collections import deque

import httpx

import health_tracker
import http_caller
import routing_engine
import telegram_bot

logger = logging.getLogger(__name__)

_chat_histories: dict[str, deque] = {}
_probe_task: asyncio.Task | None = None
_boot_time: float = time.time()


def _operator_error(code: str) -> str:
    return f"Command failed ({code}). Check server logs."


def _get_history(chat_id: str) -> deque:
    if chat_id not in _chat_histories:
        _chat_histories[chat_id] = deque(maxlen=10)
    return _chat_histories[chat_id]


def _optional_import(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        logger.warning("%s is not available; optional Telegram feature disabled", module_name)
        return None


async def cmd_chat(chat_id: str, message: str) -> None:
    if not message:
        await telegram_bot.send_message("Usage: /chat <message>", chat_id=chat_id)
        return
    history = _get_history(chat_id)
    history.append({"role": "user", "content": message})
    try:
        if _needs_tools(message):
            fc_caller = _optional_import("fc_caller")
            if fc_caller is not None:
                result = await fc_caller.chat_with_tools(list(history))
                answer = result.get("answer", "")
                tools_used = result.get("tools_used", [])
                if answer:
                    history.append({"role": "assistant", "content": answer})
                    suffix = f"\n\n🔧 {', '.join(tools_used)}" if tools_used else ""
                    await telegram_bot.send_message((answer + suffix) or "(empty)", chat_id=chat_id)
                    return
        result = routing_engine.route(
            query=message, messages=list(history), call_fn=http_caller.call_api,
        )
        answer = result.get("answer", "") if isinstance(result, dict) else getattr(result, "answer", str(result))
        if answer:
            history.append({"role": "assistant", "content": answer})
        await telegram_bot.send_message(answer or "(empty response)", chat_id=chat_id)
    except Exception:
        logger.exception("cmd_chat failed")
        await telegram_bot.send_message(_operator_error("chat"), chat_id=chat_id)


_TOOL_KEYWORDS = [
    "天气", "气温", "下雨", "AQI", "空气",
    "热搜", "热榜", "微博", "知乎", "百度",
    "汇率", "美元", "欧元", "日元", "换算",
    "金价", "黄金", "油价",
    "股票", "股价", "茅台", "比特币", "BTC", "ETH",
    "快递", "物流", "单号",
    "翻译", "translate",
    "新闻", "头条",
    "节假日", "放假", "上班",
    "IP", "归属地",
    "菜谱", "怎么做", "做法",
    "火车", "高铁", "车次",
    "星座", "运势",
    "农历", "黄历", "宜忌",
    "二维码", "QR",
    "短链", "缩短",
    "域名", "ICP", "备案",
    "计算", "等于多少",
    "时区", "几点",
    "BMI", "体重",
    "历史上的今天",
    "成语",
]


def _needs_tools(message: str) -> bool:
    """判断消息是否需要调用工具（关键词匹配）。"""
    msg_lower = message.lower()
    return any(kw.lower() in msg_lower for kw in _TOOL_KEYWORDS)


async def cmd_clear(chat_id: str) -> None:
    _chat_histories.pop(chat_id, None)
    await telegram_bot.send_message("History cleared.", chat_id=chat_id)


async def cmd_code(chat_id: str, message: str) -> None:
    if not message:
        await telegram_bot.send_message("Usage: /code <prompt>", chat_id=chat_id)
        return
    try:
        import code_orchestrator
        result = code_orchestrator.handle(
            query=message,
            messages=[{"role": "user", "content": message}],
            call_fn=http_caller.call_api,
            max_tokens=2048,
        )
        answer = result.get("answer", "")
        backend = result.get("backend", "unknown")
        score = result.get("score", "?")
        text = (answer or "(empty)") + f"\n\nvia `{backend}` (score: {score})"
        await telegram_bot.send_message(text, chat_id=chat_id)
    except ImportError:
        await telegram_bot.send_message("code_orchestrator not available", chat_id=chat_id)
    except Exception:
        logger.exception("cmd_code failed")
        await telegram_bot.send_message(_operator_error("code"), chat_id=chat_id)


async def cmd_top(chat_id: str) -> None:
    try:
        load = subprocess.run(
            ["cat", "/proc/loadavg"], capture_output=True, text=True, timeout=5,
        ).stdout.strip().split()[:3]
        mem = subprocess.run(
            ["free", "-h", "--si"], capture_output=True, text=True, timeout=5,
        ).stdout.strip().split("\n")[1].split()
        conns = subprocess.run(
            ["ss", "-tn", "state", "established", "sport", "=", ":8080"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().count("\n")
        text = (
            f"Load: {' '.join(load)}\n"
            f"Mem: {mem[2]} used / {mem[1]} total\n"
            f"Connections: {conns}"
        )
        await telegram_bot.send_message(text, chat_id=chat_id)
    except Exception:
        logger.exception("cmd_top failed")
        await telegram_bot.send_message(_operator_error("top"), chat_id=chat_id)


async def cmd_uptime(chat_id: str) -> None:
    try:
        r = subprocess.run(
            ["systemctl", "show", "lima-router", "-p", "ActiveEnterTimestamp"],
            capture_output=True, text=True, timeout=5,
        )
        ts_str = r.stdout.strip().split("=", 1)[-1].strip()
        elapsed = int(time.time() - _boot_time)
        h, m = elapsed // 3600, (elapsed % 3600) // 60
        text = f"Uptime: {h}h {m}m\nStarted: {ts_str or 'unknown'}"
        await telegram_bot.send_message(text, chat_id=chat_id)
    except Exception:
        logger.exception("cmd_uptime failed")
        await telegram_bot.send_message(_operator_error("uptime"), chat_id=chat_id)


async def cmd_eval(chat_id: str, backend: str) -> None:
    if not backend:
        await telegram_bot.send_message("Usage: /eval <backend>", chat_id=chat_id)
        return
    await telegram_bot.send_message("Evaluating...", chat_id=chat_id)
    try:
        prompt = [{"role": "user", "content": "Write a Python function that reverses a string. Return only code."}]
        result = http_caller.call_api(backend, prompt, 512)
        answer = result.get("answer", "") if isinstance(result, dict) else getattr(result, "answer", str(result))
        if "def " in answer and "return" in answer:
            verdict = "PASSED"
        elif "def " in answer or "return" in answer:
            verdict = "WEAK"
        else:
            verdict = "FAILED"
        await telegram_bot.send_message(f"`{backend}`: {verdict}", chat_id=chat_id)
    except Exception:
        logger.exception("cmd_eval failed")
        await telegram_bot.send_message(_operator_error("eval"), chat_id=chat_id)


async def cmd_task(chat_id: str, goal: str) -> None:
    if not goal:
        await telegram_bot.send_message("Usage: /task <goal>", chat_id=chat_id)
        return
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            admin = os.environ.get("LIMA_ADMIN_TOKEN", "")
            r = await c.post(
                "http://127.0.0.1:8080/agent/tasks",
                headers={"Authorization": f"Bearer {admin}"},
                json={
                    "repo": ".",
                    "branch": "main",
                    "goal": goal,
                    "mode": "patch",
                    "allowed_tools": ["read", "write", "git_diff", "test"],
                    "test_commands": ["python -m pytest -x -q"],
                },
            )
            data = r.json()
            await telegram_bot.send_message(
                f"Task created: `{data.get('task_id', '?')}`", chat_id=chat_id,
            )
    except Exception:
        logger.exception("cmd_task failed")
        await telegram_bot.send_message(_operator_error("task"), chat_id=chat_id)


async def cmd_tasks(chat_id: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            admin = os.environ.get("LIMA_ADMIN_TOKEN", "")
            r = await c.get(
                "http://127.0.0.1:8080/agent/tasks?status=accepted&limit=5",
                headers={"Authorization": f"Bearer {admin}"},
            )
            data = r.json()
            tasks = data.get("tasks", [])
            if not tasks:
                await telegram_bot.send_message("No pending tasks.", chat_id=chat_id)
                return
            lines = [f"- `{t.get('task_id','')}` {t.get('goal','')[:40]}" for t in tasks]
            await telegram_bot.send_message("\n".join(lines), chat_id=chat_id)
    except Exception:
        logger.exception("cmd_tasks failed")
        await telegram_bot.send_message(_operator_error("tasks"), chat_id=chat_id)


async def cmd_cache(chat_id: str) -> None:
    import semantic_cache
    s = semantic_cache.stats()
    text = (
        f"Cache stats:\n"
        f"Memory: {s['size']} / {s['max_size']}\n"
        f"DB: {s['db_size']} entries\n"
        f"Hits: {s['hits']} | Misses: {s['misses']}\n"
        f"Hit rate: {s['hit_rate']}"
    )
    await telegram_bot.send_message(text, chat_id=chat_id)


async def cmd_stop(chat_id: str, task_id: str) -> None:
    if not task_id:
        await telegram_bot.send_message("Usage: /stop <task_id>", chat_id=chat_id)
        return
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            admin = os.environ.get("LIMA_ADMIN_TOKEN", "")
            r = await c.post(
                f"http://127.0.0.1:8080/agent/tasks/{task_id}/cancel",
                headers={"Authorization": f"Bearer {admin}"},
            )
            if r.status_code == 200:
                await telegram_bot.send_message(f"Task `{task_id}` cancelled.", chat_id=chat_id)
            else:
                await telegram_bot.send_message(_operator_error("stop"), chat_id=chat_id)
    except Exception:
        logger.exception("cmd_stop failed")
        await telegram_bot.send_message(_operator_error("stop"), chat_id=chat_id)


async def probe_backends() -> None:
    hmap = health_tracker.get_health_map()
    backends = list(hmap.keys())
    if not backends:
        return
    sample = random.sample(backends, min(5, len(backends)))
    for b in sample:
        try:
            result = http_caller.call_api(b, [{"role": "user", "content": "hi"}], 32)
            answer = result.get("answer", "") if isinstance(result, dict) else getattr(result, "answer", str(result))
            if answer:
                health_tracker.record_success(b, 1000.0)
            else:
                health_tracker.record_failure(b, error_code=500, error_text="probe empty")
        except Exception as exc:
            logger.warning(
                "telegram probe failed backend=%s err=%s",
                b,
                type(exc).__name__,
            )
            health_tracker.record_failure(b, error_code=0, error_text="probe exception")
    new_dead = [
        b for b in sample
        if hmap.get(b) != "dead" and health_tracker.get_health_map().get(b) == "dead"
    ]
    for b in new_dead:
        await telegram_bot.send_alert("critical", f"Probe: `{b}` went dead")


async def start_probe_loop() -> None:
    global _probe_task
    if _probe_task is not None:
        return

    async def _loop() -> None:
        while True:
            await asyncio.sleep(3600)
            try:
                await probe_backends()
            except Exception:
                logger.exception("Probe loop error")

    _probe_task = asyncio.create_task(_loop())


_broadcast_task: asyncio.Task | None = None


async def daily_broadcast() -> None:
    """每天早上 8:30 播报系统状态。"""
    mimo_tts = _optional_import("mimo_tts")
    hmap = health_tracker.get_health_map()
    healthy = sum(1 for v in hmap.values() if v == "healthy")
    dead = sum(1 for v in hmap.values() if v == "dead")
    total = len(hmap)

    text = (
        f"早上好！LiMa 系统播报：\n"
        f"后端状态：{healthy}/{total} 健康，{dead} 离线。\n"
        f"运行时间：{int((time.time() - _boot_time) / 3600)} 小时。"
    )
    await telegram_bot.send_message(text)
    if mimo_tts is not None:
        ogg = await mimo_tts.tts_ogg(text)
        if ogg:
            await telegram_bot.send_voice(ogg, caption="Daily Broadcast")


async def start_broadcast_loop() -> None:
    """启动定时播报循环（每天 08:30）。"""
    global _broadcast_task
    if _broadcast_task is not None:
        return

    async def _loop() -> None:
        while True:
            import datetime
            now = datetime.datetime.now()
            target = now.replace(hour=8, minute=30, second=0, microsecond=0)
            if now >= target:
                target += datetime.timedelta(days=1)
            wait_secs = (target - now).total_seconds()
            await asyncio.sleep(wait_secs)
            try:
                await daily_broadcast()
            except Exception:
                logger.exception("Broadcast error")

    _broadcast_task = asyncio.create_task(_loop())


async def cmd_voice(chat_id: str, message: str) -> None:
    """将文本转为语音发送到 Telegram。"""
    if not message:
        await telegram_bot.send_message("Usage: /voice <text>", chat_id=chat_id)
        return
    await telegram_bot.send_message("Generating voice...", chat_id=chat_id)
    try:
        mimo_tts = _optional_import("mimo_tts")
        if mimo_tts is None:
            await telegram_bot.send_message("Voice backend not available", chat_id=chat_id)
            return
        ogg = await mimo_tts.tts_ogg(message)
        if not ogg:
            await telegram_bot.send_message("TTS failed (no audio returned)", chat_id=chat_id)
            return
        ok = await telegram_bot.send_voice(ogg, chat_id=chat_id, caption=message[:100])
        if not ok:
            await telegram_bot.send_message("Failed to send voice message", chat_id=chat_id)
    except Exception:
        logger.exception("cmd_voice failed")
        await telegram_bot.send_message(_operator_error("voice"), chat_id=chat_id)


async def cmd_voicechat(chat_id: str, arg: str) -> None:
    """切换 voicechat 模式：回复同时带语音。"""
    from routes.telegram import _voicechat_enabled
    current = _voicechat_enabled.get(chat_id, False)
    if arg.lower() in ("on", "1", "true"):
        _voicechat_enabled[chat_id] = True
        await telegram_bot.send_message("Voicechat ON — replies will include voice", chat_id=chat_id)
    elif arg.lower() in ("off", "0", "false"):
        _voicechat_enabled[chat_id] = False
        await telegram_bot.send_message("Voicechat OFF", chat_id=chat_id)
    else:
        _voicechat_enabled[chat_id] = not current
        state = "ON" if not current else "OFF"
        await telegram_bot.send_message(f"Voicechat {state}", chat_id=chat_id)


async def cmd_github(chat_id: str, args: str) -> None:
    from telegram_operator_tools import fetch_github_file_text, parse_github_args

    parsed = parse_github_args(args)
    if not parsed:
        await telegram_bot.send_message(
            "Usage: /github owner/repo path/to/file [ref]",
            chat_id=chat_id,
        )
        return
    repo, path, ref = parsed
    try:
        text = fetch_github_file_text(repo, path, ref)
        await telegram_bot.send_message(text, chat_id=chat_id, parse_mode="")
    except Exception:
        logger.exception("cmd_github failed")
        await telegram_bot.send_message(_operator_error("github"), chat_id=chat_id)


async def cmd_device(chat_id: str, args: str) -> None:
    from telegram_operator_tools import append_recent_tasks_summary, fetch_device_gateway_status

    sub = (args or "status").strip().lower()
    if sub not in ("status", ""):
        await telegram_bot.send_message(
            "Usage: /device status",
            chat_id=chat_id,
        )
        return
    try:
        summary = await fetch_device_gateway_status()
        lines = summary.splitlines()
        append_recent_tasks_summary(lines)
        await telegram_bot.send_message("\n".join(lines), chat_id=chat_id, parse_mode="")
    except Exception:
        logger.exception("cmd_device failed")
        await telegram_bot.send_message(_operator_error("device"), chat_id=chat_id)
