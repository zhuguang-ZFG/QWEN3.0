"""Tests for public static file routing."""

from __future__ import annotations

from pathlib import Path

import pytest

from routes import static_files


def test_chat_index_candidates_prefer_tracked_site_page() -> None:
    candidates = static_files._chat_index_candidates()

    assert candidates[0] == Path(static_files._BASE_DIR / "donglicao-site" / "chat.html")
    assert candidates[1] == Path(static_files._BASE_DIR / "data" / "chat" / "index.html")


@pytest.mark.asyncio
async def test_serve_index_prefers_donglicao_site(monkeypatch) -> None:
    preferred = static_files._BASE_DIR / "donglicao-site" / "chat.html"
    fallback = static_files._BASE_DIR / "data" / "chat" / "index.html"
    monkeypatch.setattr(static_files, "_chat_index_candidates", lambda: [preferred, fallback])

    response = await static_files.serve_index()

    assert str(response.path) == str(preferred)
