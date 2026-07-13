"""Tests for FIX-I: text input length upper bound validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from dlc_core.write import handle_write
from device_gateway.device_write_handler import handle_device_write
from device_gateway.handwriting_path import try_text_to_handwriting
from device_gateway.intent import parse_command


# ── dlc_core/write.py ────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("dlc_core.write._handle_device_write")
async def test_handle_write_normal_length(mock_dw):
    """Normal-length text should pass through."""
    mock_dw.return_value = {
        "status": "success",
        "path_data": [],
        "preview_svg": "",
        "width": 0,
        "height": 0,
        "model": "deterministic",
        "error": None,
    }
    text = "A" * 5000
    result = await handle_write(text)
    assert result["status"] == "success"
    mock_dw.assert_called_once()


@pytest.mark.asyncio
@patch("dlc_core.write._handle_device_write")
async def test_handle_write_overlong(mock_dw):
    """Text exceeding MAX_TEXT_LENGTH should be rejected without calling downstream."""
    text = "A" * 5001
    result = await handle_write(text)
    assert result["status"] == "failed"
    assert "too long" in (result.get("error") or "")
    mock_dw.assert_not_called()


# ── device_gateway/device_write_handler.py ───────────────────────────


@pytest.mark.asyncio
async def test_handle_device_write_normal_length():
    """Normal-length text should succeed."""
    result = await handle_device_write("Hello World", device_id="test-1")
    assert result["status"] == "success"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_handle_device_write_overlong():
    """Overlong text should be rejected."""
    text = "A" * 5001
    result = await handle_device_write(text, device_id="test-1")
    assert result["status"] == "failed"
    assert "too long" in (result.get("error") or "")


# ── device_gateway/handwriting_path.py ────────────────────────────────


def test_try_text_to_handwriting_normal():
    """Normal text with write prefix should return a result dict."""
    result = try_text_to_handwriting("写：Hello", device_id="test-1")
    # May be None if font not available, just verify no error
    if result:
        assert isinstance(result, dict)


def test_try_text_to_handwriting_overlong():
    """Overlong text should return None (refuse to process)."""
    text = "写：" + "A" * 5001
    result = try_text_to_handwriting(text, device_id="test-1")
    assert result is None


# ── device_gateway/intent.py ──────────────────────────────────────────


def test_parse_move_abs_normal():
    """Normal coordinate should match move_abs."""
    result = parse_command("move to x 123 y 456")
    assert result["capability"] == "move_abs"
    assert result["params"]["x"] == 123.0
    assert result["params"]["y"] == 456.0


def test_parse_move_abs_overflow():
    """100-digit coordinate should NOT match move_abs (digit limit {1,10})."""
    huge_x = "1" * 100
    result = parse_command(f"move to x {huge_x} y 1")
    # Falls back to write_text because move_abs doesn't match
    assert result["capability"] != "move_abs"


def test_parse_move_rel_normal():
    """Normal relative move should match."""
    result = parse_command("move x 10 y 20")
    assert result["capability"] == "move_rel"
    assert result["params"]["dx"] == 10.0
    assert result["params"]["dy"] == 20.0


def test_parse_move_rel_overflow():
    """100-digit dx should NOT match move_rel."""
    huge = "9" * 100
    result = parse_command(f"move x {huge} y 1")
    assert result["capability"] != "move_rel"
