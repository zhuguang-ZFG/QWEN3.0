"""Feedback bridge — connects route() completion to the request log.

Called at the end of every route() to persist per-request telemetry.
This is the critical link between the forward path (routing) and the
feedback path (ML training).
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def on_request_complete(
    request_id: str = "",
    scenario: str = "",
    messages: list[dict] | None = None,
    backend: str = "",
    success: bool = True,
    latency_ms: float = 0.0,
    quality_score: float = 0.0,
    fallback_used: bool = False,
    error_class: str = "",
    tokens_prompt: int = 0,
    tokens_completion: int = 0,
) -> None:
    """Record a completed request in the request log and update routing weights.

    This is the single entry point for all post-route feedback. Every
    route() call should invoke this at the end, regardless of how it
    routed (code orchestrator, speculative, normal, etc.).
    """
    try:
        from routing_loop.request_store import get_request_store
        from routing_ml.feature_extractor import extract_features

        # Compute real features from actual messages
        feature_vec = extract_features(
            messages or [], scenario=scenario,
        )
        feature_list = feature_vec.features

        # Compute message-level metrics (safe encoding)
        text = " ".join(
            str(m.get("content", "")) for m in (messages or [])
            if isinstance(m, dict)
        ).encode("utf-8", errors="replace").decode("utf-8")
        message_length = len(text)

        # Count code blocks
        import re
        try:
            code_fences = re.findall(r"```[\s\S]*?```", text)
            code_chars = sum(len(f) for f in code_fences)
            code_ratio = code_chars / max(message_length, 1)

            # Chinese ratio
            chinese_chars = len(re.findall(r"[一-鿿]", text))
            chinese_ratio = chinese_chars / max(message_length, 1)
        except Exception:
            code_ratio = 0.0
            chinese_ratio = 0.0

        # Persist to request log
        store = get_request_store()
        store.log_request(
            request_id=request_id,
            scenario=scenario,
            message_length=message_length,
            code_ratio=code_ratio,
            chinese_ratio=chinese_ratio,
            feature_vector=feature_list,
            backend=backend,
            success=success,
            latency_ms=latency_ms,
            quality_score=quality_score,
            fallback_used=fallback_used,
            error_class=error_class,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
        )

        # Also update routing weights (backward compatible)
        _update_routing_weights(backend, scenario, success)

        # Increment ML training counter
        _check_training_trigger()

    except Exception as exc:
        import logging as _dbg
        _dbg.getLogger(__name__).warning(
            "feedback_bridge.on_request_complete FAILED: %s: %s",
            type(exc).__name__, exc, exc_info=True,
        )


def _update_routing_weights(backend: str, scenario: str, success: bool) -> None:
    """Update the GRPO-style routing weights (existing system)."""
    try:
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        if success:
            rw.record_success(backend, scenario)
        else:
            rw.record_failure(backend, scenario)
    except Exception:
        pass


_request_counter = 0
_TRAINING_INTERVAL = 500


def _check_training_trigger() -> None:
    """Increment counter and trigger ML training at threshold."""
    global _request_counter
    _request_counter += 1
    if _request_counter >= _TRAINING_INTERVAL:
        _request_counter = 0
        try:
            from routing_loop.loop_closer import close_loop
            close_loop()
        except Exception as exc:
            _log.debug("loop_closer.close_loop failed: %s", exc)


def get_request_count() -> int:
    """Return the current request counter (for diagnostics)."""
    return _request_counter
