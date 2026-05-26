"""Tests for 60s hot/news channel APIs."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_gateway.public_apis import fetch_hot_60s, fetch_news_60s


def test_fetch_hot_60s_normalizes_vvhan_shape(monkeypatch):
    def fake_get(url: str) -> dict:
        return {
            "success": True,
            "data": [
                {"title": "话题A", "hot": "999万"},
                {"title": "话题B", "hot": "888万"},
            ],
        }

    monkeypatch.setattr("channel_gateway.public_apis._get_json", fake_get)
    result = fetch_hot_60s("微博")
    assert result["ok"] is True
    assert "话题A" in result["text"]
    assert "999万" in result["text"]


def test_fetch_news_60s_daily_briefing(monkeypatch):
    def fake_get(url: str) -> dict:
        return {
            "success": True,
            "data": {
                "date": "2026-05-26",
                "news": ["第一条", "第二条"],
            },
        }

    monkeypatch.setattr("channel_gateway.public_apis._get_json", fake_get)
    result = fetch_news_60s()
    assert result["ok"] is True
    assert "2026-05-26" in result["text"]
    assert "第一条" in result["text"]
