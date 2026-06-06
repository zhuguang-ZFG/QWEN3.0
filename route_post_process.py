"""Post-route integrations extracted from routing_engine (CQ-014 slice)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _warn(stage: str, exc: BaseException) -> None:
    logger.warning("post-route %s failed: %s", stage, exc, exc_info=True)


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
        and backends
        and final_backend != backends[0]
    )

    if fallback_used and answer:
        try:
            from context_pipeline.narrative import reframe_for_handoff
            reframe_for_handoff(messages_injected, backends[0], final_backend)
        except ImportError:
            logger.debug("route_post_process: optional module not available", exc_info=True)
        except Exception as exc:
            _warn("narrative", exc)

    try:
        from context_pipeline.hierarchical_memory import get_hierarchical_memory
        hmem = get_hierarchical_memory()
        hmem.update_performance(final_backend, ms, bool(answer))
        hmem.set_global_fact(f"last_scenario:{scenario}", final_backend)
        if ms > 0:
            hmem.save()
    except ImportError:
        logger.debug("route_post_process: optional module not available", exc_info=True)
    except Exception as exc:
        _warn("hierarchical_memory", exc)

    try:
        from context_pipeline.routing_bridge import record_routing_outcome
        record_routing_outcome(final_backend, ms, bool(answer), scenario)
    except ImportError:
        logger.debug("route_post_process: optional module not available", exc_info=True)
    except Exception as exc:
        _warn("routing_bridge", exc)

    try:
        if answer and scenario == "coding":
            from context_pipeline.session_memory_enhancer import process_session_outcome
            process_session_outcome(
                messages, backend=final_backend, scenario=scenario, success=bool(answer),
            )
    except Exception as exc:
        _warn("session_memory_enhancer", exc)

    # Cloud services logging (Supabase + LangSmith)
    try:
        from integrations.cloud_services import log_llm_run, log_routing_decision
        log_routing_decision(final_backend, req_type, scenario, ms, fallback_used)
        log_llm_run(final_backend, final_backend, ms, scenario=scenario)
    except Exception as cloud_exc:
        import logging as _cl
        _cl.getLogger(__name__).debug("cloud_services failed: %s", cloud_exc)

    try:
        from context_pipeline.response_pipeline import ResponseContext
        from context_pipeline.response_processors import build_default_response_pipeline
        resp_ctx = build_default_response_pipeline().process(ResponseContext(
            backend=final_backend,
            response_text=answer or "",
            latency_ms=ms,
            status_code=200 if answer else 500,
        ))
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        if resp_ctx.quality_ok and final_backend not in ("exhausted", "none", "cache"):
            rw.record_success(final_backend, scenario)
        elif final_backend not in ("exhausted", "none", "cache"):
            rw.record_failure(final_backend, scenario)
        if resp_ctx.quality_ok and answer and final_backend not in ("exhausted", "none", "cache"):
            from context_pipeline.skill_store import get_skill_store
            get_skill_store().crystallize(messages, scenario, final_backend, 0, ms)
    except ImportError:
        logger.debug("route_post_process: optional module not available", exc_info=True)
    except Exception as exc:
        _warn("response_pipeline", exc)

    try:
        from observability.events import route_decision_event
        from observability.metrics import record as obs_record
        suffix = "/fallback" if fallback_used else ""
        obs_record(route_decision_event(
            "",
            final_backend,
            f"{req_type}/{scenario}{suffix}",
            candidates=backends if backends else [],
        ))
    except ImportError:
        logger.debug("route_post_process: optional module not available", exc_info=True)
    except Exception as exc:
        _warn("observability", exc)
