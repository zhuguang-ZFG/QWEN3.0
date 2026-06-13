# LiMa Observability Events

> Created: 2026-05-24
> Scope: local, zero-dependency observability event and metrics model.

## Goals

- Explain backend routing, failure, latency, quality, and token telemetry.
- Keep default observability local and in memory.
- Avoid raw prompt, key, cookie, file body, and secret persistence.
- Provide stable helper functions before wiring hot request paths.

## Event Shape

`observability.events.LiMaEvent` contains:

- `event_type`
- `timestamp`
- `request_id`
- `session_id_hash`
- `backend`
- `route_reason`
- `latency_ms`
- `failure_class`
- `quality_score`
- `cost_class`
- `prompt_tokens`
- `completion_tokens`
- `metadata`

`session_id_hash` is a short SHA-256 hash. The original session id is not
stored.

## Event Factories

- `request_start_event()`
- `request_end_event()`
- `backend_call_event()`
- `backend_error_event()`
- `route_decision_event()`
- `quality_result_event()`
- `key_pool_event()`
- `token_usage_event()`

## Redaction Rules

Event construction sanitizes metadata recursively.

Sensitive metadata keys are replaced with `[REDACTED]`, including prompt,
message, key, token, cookie, password, secret, authorization, body, and
file-body shaped fields.

String values are passed through the shared memory redactor when available.
This keeps event objects safe even if a caller accidentally passes a token-like
value into `metadata` or `key_pool_event(details=...)`.

## Metrics Snapshot

`observability.metrics.get_metrics_snapshot()` returns:

- total request count;
- active hashed-session count;
- per-backend success/failure count;
- per-backend average, p50, and p95 latency;
- per-backend average quality score;
- per-backend prompt/completion token totals;
- failure-class counts;
- event-type counts.

Convenience queries:

- `get_top_failing_backends(n)`
- `get_top_quality_backends(n)`
- `get_fastest_growing_failure_class(n)`

## Current Boundary

M6 defines the event model, local metrics sink, report, tests, and hot-path
wiring for:

- `http_caller.py`
- `routing_engine.py`
- `routes/quality_gate.py`
- `key_pool.py`
- `budget_manager.py`

No exporter, network call, Prometheus dependency, or third-party telemetry sink
is enabled by default.
