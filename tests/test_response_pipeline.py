from context_pipeline.response_pipeline import ResponseContext, ResponsePipeline
from context_pipeline.response_processors import (
    build_default_response_pipeline,
    event_recording_processor,
    lesson_extraction_processor,
    memory_capture_processor,
    quality_check_processor,
)


def test_quality_check_empty_response():
    ctx = ResponseContext(backend="groq", response_text="", latency_ms=100)
    ctx = quality_check_processor(ctx)
    assert ctx.quality_ok is False
    assert "empty_response" in ctx.quality_issues


def test_quality_check_garbled():
    ctx = ResponseContext(backend="x", response_text="hello ���� world ����", latency_ms=100)
    ctx = quality_check_processor(ctx)
    assert ctx.quality_ok is False
    assert "garbled_encoding" in ctx.quality_issues


def test_quality_check_good_response():
    ctx = ResponseContext(backend="scnet", response_text="Here is the fix for your bug...", latency_ms=500)
    ctx = quality_check_processor(ctx)
    assert ctx.quality_ok is True
    assert ctx.quality_issues == []


def test_quality_check_http_error():
    ctx = ResponseContext(backend="x", response_text="error", status_code=502)
    ctx = quality_check_processor(ctx)
    assert ctx.quality_ok is False
    assert "http_502" in ctx.quality_issues


def test_memory_capture_extracts_summary():
    ctx = ResponseContext(backend="scnet_qwen72b", response_text="The bug is on line 42.\nMore details here.")
    ctx = memory_capture_processor(ctx)
    assert "scnet_qwen72b" in ctx.summary
    assert "line 42" in ctx.summary


def test_memory_capture_empty_response():
    ctx = ResponseContext(backend="x", response_text="")
    ctx = memory_capture_processor(ctx)
    assert ctx.summary == ""


def test_lesson_extraction_on_failure():
    ctx = ResponseContext(backend="groq_llama70b", response_text="", latency_ms=12000)
    ctx.quality_ok = False
    ctx.quality_issues = ["empty_response"]
    ctx = lesson_extraction_processor(ctx)
    assert "groq_llama70b" in ctx.lesson
    assert "empty_response" in ctx.lesson
    assert "12000ms" in ctx.lesson


def test_lesson_extraction_skips_success():
    ctx = ResponseContext(backend="scnet", response_text="ok")
    ctx.quality_ok = True
    ctx = lesson_extraction_processor(ctx)
    assert ctx.lesson == ""


def test_default_response_pipeline_full_flow():
    pipe = build_default_response_pipeline()
    ctx = pipe.process(ResponseContext(
        backend="scnet_qwen72b",
        response_text="Fixed the routing bug by updating line 42.",
        latency_ms=800,
    ))
    assert ctx.quality_ok is True
    assert "scnet_qwen72b" in ctx.summary
    assert ctx.lesson == ""
    assert len(ctx.processors_applied) == 5


def test_default_response_pipeline_failure_flow():
    pipe = build_default_response_pipeline()
    ctx = pipe.process(ResponseContext(
        backend="groq_llama70b",
        response_text="",
        latency_ms=15000,
        status_code=200,
    ))
    assert ctx.quality_ok is False
    assert "groq_llama70b" in ctx.lesson
    assert len(ctx.processors_applied) == 5
