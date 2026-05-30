"""Telegram operator tools — coding eval slice trigger."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

import telegram_bot
from eval_quiet import set_eval_quiet
from eval_slice_summary import latest_scores_path, summarize_eval_json
from routes.telegram_commands import _operator_error

_log = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parent.parent
_PLAIN = ""

_eval_busy = False
_eval_lock = asyncio.Lock()


def eval_auto_archive_enabled() -> bool:
    return os.environ.get("LIMA_EVAL_AUTO_ARCHIVE_TG", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _run_eval_slice(*, quick: bool = True) -> tuple[int, str]:
    script = _ROOT / "scripts" / "run_radar_eval_slice.py"
    if not script.is_file():
        return 2, f"missing script: {script.name}"
    cmd = [sys.executable, str(script), "--preflight"]
    if quick:
        cmd.append("--quick")
    else:
        cmd.append("--full")
    proc = subprocess.run(
        cmd,
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    tail = "\n".join(
        line for line in (proc.stdout or "").splitlines()[-6:]
        if line.strip()
    )
    if proc.returncode != 0 and not tail:
        tail = (proc.stderr or "").strip()[-400:]
    return proc.returncode, tail


async def _archive_eval_to_chat(
    chat_id: str,
    path: Path,
    *,
    full: bool,
    send_doc: bool,
) -> None:
    top = 11 if full else 5
    body = summarize_eval_json(path, top_n=top)
    label = f"eval-{'full' if full else 'quick'}:{path.name}"
    from telegram_archive import format_archive_message, chunk_text

    message = format_archive_message(label, body)
    parts = chunk_text(message)
    for idx, part in enumerate(parts, start=1):
        prefix = f"({idx}/{len(parts)})\n" if len(parts) > 1 else ""
        await telegram_bot.send_message(prefix + part, chat_id=chat_id, parse_mode="")
    doc_ok = False
    if send_doc:
        doc_ok = await telegram_bot.send_document(
            path,
            chat_id=chat_id,
            caption=f"[TG-ARCHIVE] {label}",
            filename=path.name,
        )
    suffix = f"· {path.name}"
    if send_doc:
        suffix += " · document ok" if doc_ok else " · document failed"
    else:
        suffix += "（加 doc 可上传 JSON 文件）"
    await telegram_bot.send_message(
        f"已归档到本 chat 历史（TG 冷存储 v0.2）{suffix}",
        chat_id=chat_id,
        parse_mode=_PLAIN,
    )


async def _evalslice_worker(chat_id: str, *, quick: bool) -> None:
    global _eval_busy
    set_eval_quiet(True)

    from routes.telegram_cards import LiveStatusCard

    label_cn = "快速评测" if quick else "全量评测"
    card = LiveStatusCard(f"Eval {label_cn}", chat_id)
    card.add(f"模式: {'Quick 3x3' if quick else 'Full 11-backend'}")
    msg_id = await card.send()
    if msg_id is None:
        msg_id = 0

    try:
        await card.update(msg_id, "run")
        code, log_tail = await asyncio.to_thread(_run_eval_slice, quick=quick)
        if code == 0:
            summary = ""
            path = latest_scores_path(_ROOT / "data", full=not quick)
            if path:
                try:
                    summary = summarize_eval_json(path)
                except Exception:
                    _log.warning("eval slice summary failed path=%s", path, exc_info=True)
            card.add(f"Result: OK ({summary[:200] if summary else 'no summary'})")
            await card.done(msg_id, ok=True)
            if path and eval_auto_archive_enabled():
                try:
                    await _archive_eval_to_chat(
                        chat_id, path, full=not quick, send_doc=not quick,
                    )
                except Exception:
                    _log.warning("eval auto archive failed", exc_info=True)
        else:
            detail = log_tail or ""
            if "eval_preflight_fail" in detail:
                hint = "/health or LIMA_EVAL_BASE_URL issue"
            elif "missing script" in detail:
                hint = "VPS missing eval script"
            else:
                hint = "check journalctl"
            card.add(f"Error: exit={code} {detail[:200]}")
            card.add(f"Hint: {hint}")
            await card.done(msg_id, ok=False)
    except Exception:
        _log.exception("evalslice worker failed")
        await telegram_bot.send_message(_operator_error("evalslice"), chat_id=chat_id)
    finally:
        set_eval_quiet(False)
        _eval_busy = False


async def cmd_evalslice(chat_id: str, args: str) -> None:
    global _eval_busy
    async with _eval_lock:
        if _eval_busy:
            await telegram_bot.send_message(
                "已有 Eval 运行中，请等待上一条完成消息（full 约 3–8 分钟）",
                chat_id=chat_id,
                parse_mode=_PLAIN,
            )
            return
        _eval_busy = True

    mode = args.strip().lower()
    quick = mode not in ("full", "all", "11")
    label = "quick" if quick else "full-11"
    hint = "（约 3–8 分钟）" if not quick else ""
    await telegram_bot.send_message(
        f"Eval slice ({label}) 启动中{hint}…",
        chat_id=chat_id,
        parse_mode=_PLAIN,
    )
    asyncio.create_task(_evalslice_worker(chat_id, quick=quick))


async def cmd_evalreport(chat_id: str, args: str) -> None:
    mode = args.strip().lower()
    full = mode in ("full", "all", "11")
    path = latest_scores_path(_ROOT / "data", full=full)
    if not path:
        label = "full-11" if full else "quick"
        await telegram_bot.send_message(
            f"尚无 {label} eval JSON（先跑 /evalslice{' full' if full else ''}）",
            chat_id=chat_id,
            parse_mode=_PLAIN,
        )
        return
    try:
        text = summarize_eval_json(path)
        await telegram_bot.send_message(text, chat_id=chat_id, parse_mode=_PLAIN)
    except Exception:
        _log.exception("cmd_evalreport failed")
        await telegram_bot.send_message(_operator_error("evalreport"), chat_id=chat_id)


async def cmd_archiveeval(chat_id: str, args: str) -> None:
    """Write eval summary into this chat history ([TG-ARCHIVE] cold storage)."""
    mode = args.strip().lower()
    send_doc = any(token in mode.split() for token in ("doc", "file", "document"))
    full = any(token in mode.split() for token in ("full", "all", "11"))
    path = latest_scores_path(_ROOT / "data", full=full)
    if not path:
        label = "full-11" if full else "quick"
        await telegram_bot.send_message(
            f"尚无 {label} eval JSON（先跑 /evalslice{' full' if full else ''}）",
            chat_id=chat_id,
            parse_mode=_PLAIN,
        )
        return
    try:
        await _archive_eval_to_chat(
            chat_id,
            path,
            full=full,
            send_doc=send_doc,
        )
    except Exception:
        _log.exception("cmd_archiveeval failed")
        await telegram_bot.send_message(_operator_error("archiveeval"), chat_id=chat_id)


async def cmd_poolgate(chat_id: str, args: str) -> None:
    """Show eval-driven coding pool demotions."""
    from eval_pool_gate import demoted_backends, load_eval_averages, pool_gate_enabled

    if not pool_gate_enabled():
        await telegram_bot.send_message(
            "Eval pool gate 已关闭（LIMA_EVAL_POOL_GATE=0）",
            chat_id=chat_id,
            parse_mode=_PLAIN,
        )
        return
    scores = load_eval_averages(_ROOT / "data")
    if not scores:
        await telegram_bot.send_message(
            "尚无 eval JSON，无法计算 pool gate（先跑 /evalslice full）",
            chat_id=chat_id,
            parse_mode=_PLAIN,
        )
        return
    blocked = sorted(demoted_backends(_ROOT / "data"))
    lines = ["Eval pool gate（avg < min 默认 1）", f"demoted={len(blocked)}"]
    for name in blocked:
        lines.append(f"· {name}: avg={scores.get(name, 0):.0f}")
    if not blocked:
        lines.append("· （无降级 backend）")
    await telegram_bot.send_message("\n".join(lines), chat_id=chat_id, parse_mode=_PLAIN)


async def cmd_evalschedule(chat_id: str, args: str) -> None:
    from eval_notify import schedule_status_lines

    await telegram_bot.send_message(
        "\n".join(schedule_status_lines()),
        chat_id=chat_id,
        parse_mode=_PLAIN,
    )


async def cmd_evalstatus(chat_id: str, args: str) -> None:
    from eval_status import build_eval_status

    try:
        text = build_eval_status(_ROOT / "data", eval_busy=_eval_busy)
        await telegram_bot.send_message(text, chat_id=chat_id, parse_mode=_PLAIN)
    except Exception:
        _log.exception("cmd_evalstatus failed")
        await telegram_bot.send_message(_operator_error("evalstatus"), chat_id=chat_id)


async def cmd_evaldigest(chat_id: str, args: str) -> None:
    from eval_digest import build_eval_digest

    try:
        text = build_eval_digest(_ROOT / "data")
        await telegram_bot.send_message(text[:4000], chat_id=chat_id, parse_mode=_PLAIN)
    except Exception:
        _log.exception("cmd_evaldigest failed")
        await telegram_bot.send_message(_operator_error("evaldigest"), chat_id=chat_id)
