"""Slice 6: smart_router compatibility shell is re-export only."""

from __future__ import annotations

from pathlib import Path

import smart_router


def test_smart_router_reexports_analyze():
    assert smart_router.analyze("你好")["intent"]


def test_smart_router_distill_alias():
    assert smart_router._log_to_distill_queue is smart_router.log_to_distill_queue


def test_smart_router_vision_alias():
    assert smart_router._has_vision_content is smart_router.detect_vision_request


def test_smart_router_no_local_implementation():
    root = Path(__file__).resolve().parent.parent / "smart_router.py"
    text = root.read_text(encoding="utf-8")
    assert "def _quick_score" not in text
    assert "def _log_to_distill_queue" not in text
    assert "DEPRECATED" in text
