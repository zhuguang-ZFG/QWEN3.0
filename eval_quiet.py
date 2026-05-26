"""Suppress noisy Telegram health alerts during coding eval runs."""

from __future__ import annotations

_eval_quiet = False


def set_eval_quiet(active: bool) -> None:
    global _eval_quiet
    _eval_quiet = active


def eval_quiet_active() -> bool:
    return _eval_quiet
