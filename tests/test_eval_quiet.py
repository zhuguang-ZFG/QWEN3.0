"""Tests for eval quiet mode."""

from __future__ import annotations


def test_eval_quiet_toggle():
    from eval_quiet import eval_quiet_active, set_eval_quiet

    set_eval_quiet(False)
    assert eval_quiet_active() is False
    set_eval_quiet(True)
    assert eval_quiet_active() is True
    set_eval_quiet(False)
