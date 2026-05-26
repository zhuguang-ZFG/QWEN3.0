"""Tests for Telegram archive helpers."""

from __future__ import annotations

from telegram_archive import chunk_text, format_archive_message


def test_chunk_text_splits_long_body():
    body = "\n".join(f"line-{i}" for i in range(200))
    parts = chunk_text(body, limit=500)
    assert len(parts) >= 2
    assert all(len(p) <= 500 for p in parts)


def test_format_archive_message():
    text = format_archive_message("eval-full", "hello")
    assert text.startswith("[TG-ARCHIVE] eval-full")
