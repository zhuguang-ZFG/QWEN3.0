"""Response processors — individual post-response processing stages."""

import logging

from context_pipeline.response_pipeline import ResponseContext

_log = logging.getLogger(__name__)


def quality_check_processor(ctx: ResponseContext) -> ResponseContext:
    """Check response quality: empty, truncated, garbled."""
    if not ctx.response_text or not ctx.response_text.strip():
        ctx.quality_ok = False
        ctx.quality_issues.append("empty_response")
        return ctx

    text = ctx.response_text.strip()

    if len(text) < 5 and ctx.latency_ms > 5000:
        ctx.quality_ok = False
        ctx.quality_issues.append("truncated")

    if text.count("�") > 3:
        ctx.quality_ok = False
        ctx.quality_issues.append("garbled_encoding")

    repetition_threshold = 50
    if len(text) > 200:
        chunk = text[:repetition_threshold]
        if text.count(chunk) > 3:
            ctx.quality_ok = False
            ctx.quality_issues.append("repetition_loop")

    if ctx.status_code >= 400:
        ctx.quality_ok = False
        ctx.quality_issues.append(f"http_{ctx.status_code}")

    return ctx


def code_validation_processor(ctx: ResponseContext) -> ResponseContext:
    """Validate code responses: syntax check + security pattern scan."""
    if not ctx.response_text or len(ctx.response_text) < 20:
        return ctx

    try:
        from context_pipeline.response_validator import validate_response

        vr = validate_response(ctx.response_text, "")
        if not vr.passed:
            ctx.quality_ok = False
            ctx.quality_issues.extend(vr.issues[:5])
    except Exception as exc:
        _log.debug("response_processors: quality validation failed", exc_info=True)

    return ctx


def memory_capture_processor(ctx: ResponseContext) -> ResponseContext:
    """Extract response summary for session memory."""
    if not ctx.response_text:
        ctx.summary = ""
        return ctx

    text = ctx.response_text.strip()
    first_line = text.split("\n")[0][:100]
    ctx.summary = f"[{ctx.backend}] {first_line}" if ctx.backend else first_line
    return ctx


def event_recording_processor(ctx: ResponseContext) -> ResponseContext:
    """Record response event to the event log."""
    from context_pipeline.event_log import EventType, get_request_log

    log = get_request_log()
    if ctx.quality_ok:
        log.emit(
            EventType.RESPONSE_RECEIVED,
            backend=ctx.backend,
            latency_ms=ctx.latency_ms,
            length=len(ctx.response_text),
        )
    else:
        log.emit(
            EventType.RESPONSE_ERROR,
            backend=ctx.backend,
            issues=ctx.quality_issues,
            error=ctx.error,
        )
    return ctx


def lesson_extraction_processor(ctx: ResponseContext) -> ResponseContext:
    """Extract lessons from failures for future routing improvement."""
    if ctx.quality_ok:
        return ctx

    issues = ", ".join(ctx.quality_issues)
    if ctx.backend:
        ctx.lesson = f"{ctx.backend}: {issues}"
        if ctx.latency_ms > 10000:
            ctx.lesson += f" (latency: {ctx.latency_ms}ms)"
    return ctx


def semantic_quality_processor(ctx: ResponseContext) -> ResponseContext:
    """Evaluate semantic quality and record to quality history.

    Uses semantic_eval.evaluate_response() for relevance/completeness/coherence
    scoring, then records the score in quality_history for trend tracking.
    Also updates health_tracker's quality scoring.
    """
    if not ctx.response_text or not ctx.quality_ok:
        return ctx

    try:
        import quality_history
        import semantic_eval

        # Extract the original query from the response context if available
        query = getattr(ctx, "query", "") or ""

        result = semantic_eval.evaluate_response(query, ctx.response_text)

        # Record to quality history ring buffer
        if ctx.backend:
            quality_history.record_quality(ctx.backend, result.total)

            # Also feed into existing health_scoring quality system
            import health_tracker
            # Map semantic score (0-100) to existing quality scale (0.0-1.0)
            health_tracker.record_quality_score(ctx.backend, result.total / 100.0)

    except Exception as exc:
        _log.debug("semantic_quality_processor: evaluation failed", exc_info=True)

    return ctx


def build_default_response_pipeline():
    """Build the standard response processing pipeline."""
    from context_pipeline.response_pipeline import ResponsePipeline

    return (
        ResponsePipeline()
        .add("quality_check", quality_check_processor)
        .add("code_validation", code_validation_processor)
        .add("semantic_quality", semantic_quality_processor)
        .add("memory_capture", memory_capture_processor)
        .add("event_recording", event_recording_processor)
        .add("lesson_extraction", lesson_extraction_processor)
    )
