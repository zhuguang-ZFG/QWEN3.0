"""Tests for code_validation_processor in the response pipeline."""

from context_pipeline.response_pipeline import ResponseContext
from context_pipeline.response_processors import (
    code_validation_processor,
    build_default_response_pipeline,
)


def _ctx(text, backend="test_backend", status_code=200, latency_ms=500):
    return ResponseContext(
        backend=backend,
        response_text=text,
        status_code=status_code,
        latency_ms=latency_ms,
    )


class TestCodeValidationProcessor:
    def test_valid_python_keeps_quality_ok(self):
        ctx = _ctx('```python\ndef hello():\n    return "ok"\n```')
        result = code_validation_processor(ctx)
        assert result.quality_ok is True

    def test_syntax_error_marks_quality_fail(self):
        ctx = _ctx('```python\ndef hello(\n    return "ok"\n```')
        result = code_validation_processor(ctx)
        assert result.quality_ok is False
        assert any("syntax" in i.lower() for i in result.quality_issues)

    def test_security_issue_marks_quality_fail(self):
        ctx = _ctx("```python\nresult = eval(user_input)\n```")
        result = code_validation_processor(ctx)
        assert result.quality_ok is False
        assert any("security" in i.lower() for i in result.quality_issues)

    def test_shell_true_detected(self):
        ctx = _ctx('```python\nimport subprocess\nsubprocess.call("ls", shell=True)\n```')
        result = code_validation_processor(ctx)
        assert result.quality_ok is False

    def test_non_code_response_skipped(self):
        ctx = _ctx("Sure, I can help you with that. Here's a brief explanation...")
        result = code_validation_processor(ctx)
        assert result.quality_ok is True
        assert len(result.quality_issues) == 0

    def test_empty_response_skipped(self):
        ctx = _ctx("")
        result = code_validation_processor(ctx)
        assert result.quality_ok is True

    def test_short_response_skipped(self):
        ctx = _ctx("ok")
        result = code_validation_processor(ctx)
        assert result.quality_ok is True

    def test_plain_text_not_flagged(self):
        ctx = _ctx("The quick brown fox jumps over the lazy dog. " * 5)
        result = code_validation_processor(ctx)
        assert result.quality_ok is True


class TestPipelineIntegration:
    def test_pipeline_includes_code_validation(self):
        pipeline = build_default_response_pipeline()
        names = [name for name, _ in pipeline._processors]
        assert "code_validation" in names
        assert names.index("code_validation") > names.index("quality_check")

    def test_pipeline_validates_bad_code(self):
        pipeline = build_default_response_pipeline()
        ctx = _ctx("```python\ndef bad(\n```")
        result = pipeline.process(ctx)
        assert result.quality_ok is False
        assert any("syntax" in i.lower() for i in result.quality_issues)

    def test_pipeline_passes_good_code(self):
        pipeline = build_default_response_pipeline()
        ctx = _ctx('```python\ndef hello():\n    return "ok"\n```')
        result = pipeline.process(ctx)
        assert result.quality_ok is True
