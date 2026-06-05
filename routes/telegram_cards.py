r"""Operator Console cards v0.1 -- live status cards for Telegram.

Three card types:
  1. LiveStatusCard  -- eval/deploy progress that updates in-place
  2. TaskReviewCard  -- LiMa task review with Approve/Reject buttons
  3. DeviceTaskCard  -- device task lifecycle with error codes + SVG

Usage pattern:
  card = LiveStatusCard("eval", "Running full-11 eval...")
  msg_id = await card.send(chat_id)       # creates the card
  await card.update(msg_id, "3/11 done")  # edits in-place
  await card.done(msg_id, "100% passed")  # final state

All text is Chinese-localized with monospace data fields.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable

import telegram_bot

_log = logging.getLogger(__name__)

_STAGE_EMOJI = {
    "start": "⏳",   # hourglass
    "run": "▶️",  # play
    "ok": "✅",       # check
    "fail": "❌",      # cross
    "warn": "⚠️",  # warning
}


def _now() -> str:
    return time.strftime("%H:%M:%S")


# ── Card 1: Live Status (eval / deploy / task / device progress) ──

@dataclass
class LiveStatusCard:
    title: str
    chat_id: str = ""
    _lines: list[str] = field(default_factory=list)
    _started: float = 0.0

    def __post_init__(self):
        self._started = time.time()

    def add(self, text: str) -> None:
        self._lines.append(text)

    def _build(self, stage: str = "run") -> str:
        emoji = _STAGE_EMOJI.get(stage, "")
        elapsed = int(time.time() - self._started)
        header = f"{emoji} *{self.title}*  ({elapsed}s)"
        body = "\n".join(f"  {line}" for line in self._lines[-12:])
        footer = f"`{_now()}`  {'...' if stage == 'run' else stage}"
        return f"{header}\n{body}\n{footer}"

    async def send(self, chat_id: str = "") -> int | None:
        target = chat_id or self.chat_id
        msg_id = await telegram_bot.send_message_with_keyboard(
            self._build("start"), [],
            chat_id=target, parse_mode="Markdown",
        )
        return msg_id

    async def update(self, message_id: int, stage: str = "run") -> bool:
        return await telegram_bot.edit_message_text(
            self._build(stage), message_id, parse_mode="Markdown",
        )

    async def done(self, message_id: int, ok: bool = True) -> bool:
        stage = "ok" if ok else "fail"
        return await telegram_bot.edit_message_text(
            self._build(stage), message_id, parse_mode="Markdown",
        )


# ── Card 2: Task Review (LiMa plan/test/review/ship) ──

def build_task_review_card(
    task_id: str,
    goal: str = "",
    changed_files: list[str] | None = None,
    tests_passed: int = 0,
    tests_failed: int = 0,
    risks: list[str] | None = None,
    artifact_links: dict[str, str] | None = None,
    status: str = "needs_review",
) -> tuple[str, list]:
    """Build a task review card with inline Approve/Reject buttons.

    Returns (text, inline_keyboard).
    """
    status_label = {
        "needs_review": "⏳ Needs Review",
        "approved": "✅ Approved",
        "rejected": "❌ Rejected",
    }.get(status, status)

    lines = [
        f"*Task `{task_id}`*  {status_label}",
        "",
    ]
    if goal:
        lines.append(f"\U0001f3af {goal[:200]}")
        lines.append("")

    if changed_files:
        files = changed_files[:10]
        lines.append(f"\U0001f4c1 Files ({len(changed_files)}):")
        for f in files:
            lines.append(f"  `{f[:60]}`")
        if len(changed_files) > 10:
            lines.append(f"  ... +{len(changed_files) - 10} more")
        lines.append("")

    if tests_passed or tests_failed:
        test_line = f"\U0001f9ea Tests: {tests_passed} passed"
        if tests_failed:
            test_line += f", {tests_failed} failed"
        lines.append(test_line)
        lines.append("")

    if risks:
        lines.append("⚠️ Risks:")
        for r in risks[:5]:
            lines.append(f"  - {r[:80]}")
        lines.append("")

    if artifact_links:
        links = [f"  [{k}]({v})" for k, v in artifact_links.items() if v]
        if links:
            lines.append("\U0001f4ce Artifacts:")
            lines.extend(links[:5])
            lines.append("")

    text = "\n".join(lines)

    keyboard = [[
        {"text": "✅ Approve", "callback_data": f"approve:{task_id}"},
        {"text": "❌ Reject", "callback_data": f"reject:{task_id}"},
    ], [
        {"text": "\U0001f4cb Audit", "callback_data": f"audit:{task_id}"},
        {"text": "\U0001f4e6 Archive", "callback_data": f"archive:{task_id}"},
    ]]

    return text, keyboard


async def send_task_review(
    task_id: str,
    goal: str = "",
    changed_files: list[str] | None = None,
    tests_passed: int = 0,
    tests_failed: int = 0,
    risks: list[str] | None = None,
    artifact_links: dict[str, str] | None = None,
    status: str = "needs_review",
    chat_id: str = "",
) -> int | None:
    """Send a task review card. Returns message_id."""
    text, keyboard = build_task_review_card(
        task_id=task_id, goal=goal, changed_files=changed_files,
        tests_passed=tests_passed, tests_failed=tests_failed,
        risks=risks, artifact_links=artifact_links, status=status,
    )
    return await telegram_bot.send_message_with_keyboard(
        text, keyboard, chat_id=chat_id, parse_mode="Markdown",
    )


# ── Card 3: Device Task Card (lifecycle with error codes) ──

_device_error_help = {
    "E_MISSING_PATH": "task params missing path data; check voice/transcript parsing",
    "E_UNSUPPORTED_BOARD": "capability not available on this board type",
    "E_INVALID_PARAMS": "parameter validation failed; check path safety bounds",
    "E_HARDWARE_FAULT": "stepper motor or limit switch hardware error",
    "E_TIMEOUT": "motion execution timed out; check mechanical load",
}


def build_device_task_card(
    task_id: str,
    capability: str = "",
    phase: str = "queued",
    progress_pct: int = 0,
    error_code: str = "",
    error_message: str = "",
    preview_svg: str = "",
    device_id: str = "",
    elapsed_ms: int = 0,
) -> str:
    """Build a device task progress card."""
    phase_emoji = {
        "queued": "⏳", "accepted": "✅", "running": "▶️",
        "progress": "\U0001f504", "done": "✅", "failed": "❌",
        "cancelled": "⏹️", "rejected": "⛔",
    }
    emoji = phase_emoji.get(phase, "❓")

    lines = [
        f"{emoji} *Device Task `{task_id}`*",
        f"  Device: `{device_id}`" if device_id else "",
        f"  Capability: `{capability}`",
        f"  Phase: *{phase}*",
    ]

    if phase in ("progress", "running"):
        bar_len = 10
        filled = int(progress_pct / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        lines.append(f"  [{bar}] {progress_pct}%")

    if elapsed_ms:
        sec = elapsed_ms / 1000
        lines.append(f"  Elapsed: {sec:.1f}s")

    if error_code:
        lines.append(f"  Error: `{error_code}`")
        if error_message:
            lines.append(f"  Reason: {error_message[:120]}")
        help_text = _device_error_help.get(error_code)
        if help_text:
            lines.append(f"  \U0001f4d6 {help_text}")

    lines.append(f"  `{_now()}`")

    return "\n".join(line for line in lines if line)


async def send_device_task_card(
    task_id: str,
    capability: str = "",
    phase: str = "queued",
    progress_pct: int = 0,
    error_code: str = "",
    error_message: str = "",
    preview_svg: str = "",
    device_id: str = "",
    elapsed_ms: int = 0,
    chat_id: str = "",
) -> int | None:
    """Send a device task card. Returns message_id for live updates."""
    text = build_device_task_card(
        task_id=task_id, capability=capability, phase=phase,
        progress_pct=progress_pct, error_code=error_code,
        error_message=error_message, preview_svg=preview_svg,
        device_id=device_id, elapsed_ms=elapsed_ms,
    )
    return await telegram_bot.send_message_with_keyboard(
        text, [], chat_id=chat_id, parse_mode="Markdown",
    )
