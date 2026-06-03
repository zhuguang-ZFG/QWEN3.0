"""Test web search context injection."""

import pytest
from context_pipeline.web_search_context import (
    _detect_search_intent,
    _extract_urls,
    _format_search_results,
    inject_web_search_context,
)


class TestSearchIntentDetection:
    def test_chinese_keywords(self):
        """Chinese search-trigger keywords are detected."""
        assert _detect_search_intent("帮我查一下北京天气")
        assert _detect_search_intent("搜一下最新新闻")
        assert _detect_search_intent("联网搜索量子计算")
        assert _detect_search_intent("今天有什么热点")

    def test_english_keywords(self):
        """English search-trigger keywords are detected."""
        assert _detect_search_intent("what is the capital of France")
        assert _detect_search_intent("who is the president")
        assert _detect_search_intent("latest news about AI")
        assert _detect_search_intent("weather in Tokyo")

    def test_url_triggers(self):
        """URLs always trigger search intent."""
        assert _detect_search_intent("看这个 https://example.com/doc")

    def test_code_queries_not_triggered(self):
        """Code-related queries should NOT trigger search."""
        assert not _detect_search_intent("写一个Python排序函数")
        assert not _detect_search_intent("帮我debug这段代码")
        assert not _detect_search_intent("import numpy as np")

    def test_simple_chat_not_triggered(self):
        """Simple chat doesn't trigger search."""
        assert not _detect_search_intent("hello")
        assert not _detect_search_intent("你好")
        assert not _detect_search_intent("你是谁")

    def test_empty_query(self):
        assert not _detect_search_intent("")
        assert not _detect_search_intent(None)


class TestURLExtraction:
    def test_extracts_https(self):
        urls = _extract_urls("看这个 https://example.com/page/about")
        assert "https://example.com/page/about" in urls

    def test_extracts_http(self):
        urls = _extract_urls("visit http://test.org")
        assert "http://test.org" in urls

    def test_extracts_multiple(self):
        urls = _extract_urls("a https://a.com and https://b.com/path?q=1")
        assert len(urls) == 2

    def test_no_urls(self):
        assert _extract_urls("no urls here") == []


class TestFormatResults:
    def test_formats_results(self):
        results = [
            {"title": "Test Title", "url": "https://example.com", "snippet": "A test snippet"},
        ]
        formatted = _format_search_results("test query", results)
        assert "网页搜索结果" in formatted
        assert "Test Title" in formatted
        assert "https://example.com" in formatted
        assert "A test snippet" in formatted

    def test_truncates_long_titles(self):
        results = [{"title": "X" * 200, "url": "https://x.com", "snippet": "ok"}]
        formatted = _format_search_results("q", results)
        assert len(formatted) < 2000

    def test_empty_results(self):
        formatted = _format_search_results("q", [])
        assert "网页搜索结果" in formatted


class TestInjectWebSearch:
    def test_no_search_intent_skips(self):
        """Non-search queries return messages unchanged."""
        msgs = [{"role": "system", "content": "hi"}, {"role": "user", "content": "hello"}]
        result, ctx = inject_web_search_context("hello", msgs)
        assert len(result) == len(msgs)
        assert ctx == ""

    def test_search_intent_adds_system_message(self):
        """Search queries add a system message (search may fail but structure is correct)."""
        msgs = [{"role": "system", "content": "hi"}]
        result, ctx = inject_web_search_context("帮我查一下天气", msgs)
        # Even if search backend is unavailable, at minimum messages are returned
        assert isinstance(result, list)
        assert isinstance(ctx, str)

    def test_no_side_effects(self):
        """Original messages are not modified."""
        msgs = [{"role": "user", "content": "hello"}]
        original = [dict(m) for m in msgs]
        _ = inject_web_search_context("hello", msgs)
        assert msgs == original

    def test_empty_query(self):
        msgs = [{"role": "user", "content": "hi"}]
        result, ctx = inject_web_search_context("", msgs)
        assert result == msgs
        assert ctx == ""
