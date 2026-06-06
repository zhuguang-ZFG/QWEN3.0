"""Tests for eval quiet mode."""

from __future__ import annotations

import telegram_notify


def test_notify_health_suppressed_during_eval(monkeypatch):
    telegram_notify._health_last_notified.clear()
    from unittest.mock import patch

    from eval_quiet import set_eval_quiet

    set_eval_quiet(True)
    try:
        monkeypatch.setattr(telegram_notify.telegram_bot, "is_configured", lambda: True)
        with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
            telegram_notify.notify_health_change("x", "healthy", "degraded")
            mock_ff.assert_not_called()
    finally:
        set_eval_quiet(False)


def test_eval_quiet_toggle():
    from eval_quiet import eval_quiet_active, set_eval_quiet

    set_eval_quiet(False)
    assert eval_quiet_active() is False
    set_eval_quiet(True)
    assert eval_quiet_active() is True
    set_eval_quiet(False)
