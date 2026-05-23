"""Extended Telegram command handlers and background tasks for LiMa."""

import asyncio
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


def _get_history(chat_id: str) -> deque:
    if chat_id not in _chat_histories:
        _chat_histories[chat_id] = deque(maxlen=10)
    return _chat_histories[chat_id]


async def cmd_chat(chat_id: str, message: str) -> None:
    if not message:
        await telegram_bot.send_message("Usage: /chat <message>", chat_id=chat_id)
        return
    history = _get_history(chat_id)
    history.append({"role": "user", "content": message})
    try:
        result = routing_engine.route(
            query=message, messages=list(history), call_fn=http_caller.call_api,
        )
        answer = result.get("answer", "") if isinstance(result, dict) else getattr(result, "answer", str(result))
        if answer:
            history.append({"role": "assistant", "content": answer})
        await telegram_bot.send_message(answer or "(empty response)", chat_id=chat_id)
    except Exception as e:
        logger.exception("cmd_chat failed")
        await telegram_bot.send_message(f"Error: {e}", chat_id=chat_id)


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
    except Exception as e:
        logger.exception("cmd_code failed")
        await telegram_bot.send_message(f"Error: {e}", chat_id=chat_id)


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
    except Exception as e:
        await telegram_bot.send_message(f"Error: {e}", chat_id=chat_id)


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
    except Exception as e:
        await telegram_bot.send_message(f"Error: {e}", chat_id=chat_id)


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
    except Exception as e:
        await telegram_bot.send_message(f"Error: {e}", chat_id=chat_id)


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
                json={"repo": ".", "goal": goal, "mode": "patch"},
            )
            data = r.json()
            await telegram_bot.send_message(
                f"Task created: `{data.get('task_id', '?')}`", chat_id=chat_id,
            )
    except Exception as e:
        await telegram_bot.send_message(f"Error: {e}", chat_id=chat_id)


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
    except Exception as e:
        await telegram_bot.send_message(f"Error: {e}", chat_id=chat_id)


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
        except Exception:
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
