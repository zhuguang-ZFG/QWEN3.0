"""Post-route integrations extracted from routing_engine (CQ-014 slice)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
_log = logger


def _warn(stage: str, exc: BaseException) -> None:
    logger.warning("post-route %s failed: %s", stage, exc, exc_info=True)


def _post_narrative_reframe(
    final_backend: str, backends: list[str],
    messages_injected: list[dict], answer: str,
) -> None:
    """Reframe narrative when fallback was used."""
    fallback_used = (
        final_backend not in ("exhausted", "none")
        and backends and final_backend != backends[0]
    )
    if not (fallback_used and answer):
        return
    try:
        from context_pipeline.narrative import reframe_for_handoff
        reframe_for_handoff(messages_injected, backends[0], final_backend)
    except ImportError:
        pass
    except Exception as exc:
        _warn("narrative", exc)


def _post_routing_bridge(final_backend: str, ms: int, answer: str, scenario: str) -> None:
    """Record routing outcome."""
    try:
        from context_pipeline.routing_bridge import record_routing_outcome
        record_routing_outcome(final_backend, ms, bool(answer), scenario, skip_weights=True)
    except (ImportError, TypeError):
        pass
    except Exception as exc:
        _warn("routing_bridge", exc)


def _post_cloud_services(
    final_backend: str, req_type: str, scenario: str, ms: int, fallback_used: bool,
) -> None:
    """Log to cloud services (Supabase + LangSmith)."""
    try:
        from integrations.cloud_services import log_routing_decision, log_llm_run
        log_routing_decision(final_backend, req_type, scenario, ms, fallback_used)
        log_llm_run(final_backend, final_backend, ms, scenario=scenario)
    except Exception as cloud_exc:
        import logging as _cl
        _cl.getLogger(__name__).debug("cloud_services failed: %s", cloud_exc)


def _post_response_pipeline(
    final_backend: str, answer: str, ms: int, scenario: str,
    messages: list[dict],
) -> None:
    """Run quality scoring + routing_weights + skill_store via response pipeline."""
    try:
        from context_pipeline.response_processors import build_default_response_pipeline
        from context_pipeline.response_pipeline import ResponseContext
        resp_ctx = build_default_response_pipeline().process(ResponseContext(
            backend=final_backend, response_text=answer or "",
            latency_ms=ms, status_code=200 if answer else 500,
        ))
    except ImportError:
        return
    except Exception as exc:
        _warn("response_pipeline", exc)
        return

    # Routing weights
    try:
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        if resp_ctx.quality_ok and final_backend not in ("exhausted", "none", "cache"):
            rw.record_success(final_backend, scenario)
        elif final_backend not in ("exhausted", "none", "cache"):
            rw.record_failure(final_backend, scenario)
    except Exception as exc:
        _log.debug("route_post_process.py: {}", type(exc).__name__)

    # Skill store
    try:
        from context_pipeline.skill_store import get_skill_store
        if resp_ctx.quality_ok and answer and final_backend not in ("exhausted", "none", "cache"):
            get_skill_store().crystallize(messages, scenario, final_backend, 0, ms)
            get_skill_store().confirm_success()
        elif not resp_ctx.quality_ok:
            get_skill_store().on_failure(scenario)
    except Exception as exc:
        _log.debug("route_post_process.py: {}", type(exc).__name__)


def _post_learning_loop(
    final_backend: str, answer: str, ms: int, scenario: str, messages: list[dict],
) -> None:
    """Feed regular route() outcomes to the learning loop."""
    try:
        from session_memory.learning_loop import ingest_task_outcome, TaskOutcome
        outcome = TaskOutcome(
            task_id=f"route-{scenario}-{final_backend}",
            status="succeeded" if (answer and len(answer) > 5) else "failed",
            goal=str(messages[-1].get("content", ""))[:200] if messages else "",
            backend=final_backend, scenario=scenario, latency_ms=ms,
        )
        ingest_task_outcome(outcome)
    except Exception as exc:
        _log.debug("route_post_process.py: {}", type(exc).__name__)


def _post_observability(
    final_backend: str, req_type: str, scenario: str,
    backends: list[str], fallback_used: bool,
) -> None:
    """Emit observability metrics for the routing decision."""
    try:
        from observability.metrics import record as obs_record
        from observability.events import route_decision_event
        suffix = "/fallback" if fallback_used else ""
        obs_record(route_decision_event(
            "", final_backend, f"{req_type}/{scenario}{suffix}",
            candidates=backends if backends else [],
        ))
    except ImportError:
        pass
    except Exception as exc:
        _warn("observability", exc)


def apply_post_route_integrations(
    *,
    final_backend: str,
    answer: str,
    backends: list[str],
    messages_injected: list[dict],
    messages: list[dict],
    req_type: str,
    scenario: str,
    ms: int,
) -> None:
    """Run optional post-route side effects without failing the caller."""
    fallback_used = (
        final_backend not in ("exhausted", "none")
        and backends and final_backend != backends[0]
    )
    _post_narrative_reframe(final_backend, backends, messages_injected, answer)
    _post_routing_bridge(final_backend, ms, answer, scenario)
    _post_cloud_services(final_backend, req_type, scenario, ms, fallback_used)
    _post_response_pipeline(final_backend, answer, ms, scenario, messages)
    _post_learning_loop(final_backend, answer, ms, scenario, messages)
    _post_observability(final_backend, req_type, scenario, backends, fallback_used)
