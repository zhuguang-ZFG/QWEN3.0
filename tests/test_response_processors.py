"""Tests for context_pipeline/response_processors.py — post-response processing."""

from context_pipeline.response_processors import (
    quality_check_processor,
    memory_capture_processor,
    lesson_extraction_processor,
    build_default_response_pipeline,
)
from context_pipeline.response_pipeline import ResponseContext


def _ctx(response_text="ok", status_code=200, latency_ms=100, backend="test"):
    return ResponseContext(
        backend=backend,
        response_text=response_text,
        status_code=status_code,
        latency_ms=latency_ms,
    )


class TestQualityCheckProcessor:
    def test_valid_response_passes(self):
        ctx = _ctx("valid response content here")
        result = quality_check_processor(ctx)
        assert result.quality_ok is True

    def test_empty_response_fails(self):
        ctx = _ctx("")
        result = quality_check_processor(ctx)
        assert result.quality_ok is False
        assert "empty_response" in result.quality_issues

    def test_http_error_fails(self):
        ctx = _ctx("error msg", status_code=500)
        result = quality_check_processor(ctx)
        assert result.quality_ok is False

    def test_short_response_flagged(self):
        ctx = _ctx("ab", latency_ms=6000)
        result = quality_check_processor(ctx)
        assert result.quality_ok is False
        assert "truncated" in result.quality_issues

    def test_garbled_encoding_flagged(self):
        ctx = _ctx("normal text " + "�" * 5 + " more text")
        result = quality_check_processor(ctx)
        assert "garbled_encoding" in result.quality_issues


class TestMemoryCaptureProcessor:
    def test_empty_text(self):
        ctx = _ctx("")
        result = memory_capture_processor(ctx)
        assert result.summary == ""

    def test_captures_first_line(self):
        ctx = _ctx("hello\nworld")
        result = memory_capture_processor(ctx)
        assert "hello" in result.summary
        assert result.backend in result.summary


class TestLessonExtractionProcessor:
    def test_quality_ok_returns_unchanged(self):
        ctx = _ctx()
        result = lesson_extraction_processor(ctx)
        assert result.lesson == ""

    def test_quality_failure_extracts_lesson(self):
        ctx = _ctx("content", status_code=500)
        ctx.quality_ok = False
        ctx.quality_issues = ["http_500"]
        result = lesson_extraction_processor(ctx)
        assert "test" in result.lesson
        assert "http_500" in result.lesson


class TestBuildDefaultPipeline:
    def test_pipeline_returns_context(self):
        pipeline = build_default_response_pipeline()
        assert pipeline is not None

    def test_pipeline_processes_context(self):
        pipeline = build_default_response_pipeline()
        ctx = _ctx("valid response with enough content")
        result = pipeline.process(ctx)
        assert result is not None
        assert hasattr(result, "quality_ok")
