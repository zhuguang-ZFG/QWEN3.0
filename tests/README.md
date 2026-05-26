# LiMa Test Suite Map

> Updated: 2026-05-26  
> Filenames stay flat under `tests/`; this file is the ownership index.

## Request protocol

- `tests/test_chat_endpoints.py`, `tests/test_anthropic_*.py`, `tests/test_stream_*.py`
- `tests/test_http_body_limit.py`, `tests/test_access_guard.py`

## Routing and backends

- `test_routing_engine.py`, `tests/test_route_scorer.py`, `tests/test_coding_eval.py`
- `tests/test_backend_registry.py`, `tests/test_code_orchestrator_routing.py`
- `test_code_orchestrator.py`, `tests/test_request_pipeline_authority.py`

## Device gateway

- `tests/test_device_gateway_*.py`, `tests/test_device_intent*.py` (if present)

## Agent runtime and tasks

- `tests/test_agent_task_*.py`, `tests/test_operator_features.py`
- `tests/test_tool_gateway.py`

## Memory and retrieval

- `tests/test_production_retrieval.py`, `tests/test_context_*.py`
- `tests/test_semantic_cache.py`, `tests/test_session_memory*.py` (if present)

## Ops, security, hygiene

- `tests/test_secret_hygiene.py`, `tests/test_repo_hygiene.py`, `tests/test_admin_*.py`
- `tests/test_request_stats.py`, `tests/test_ops_metrics.py` (if present)

## Channel gateway

- `tests/test_channel_*.py`, `tests/test_channel_gateway_*.py`

## Running

```powershell
python -m pytest -q --ignore=active_model
```

Focused slice example:

```powershell
python -m pytest tests/test_request_pipeline_authority.py test_code_orchestrator.py -q --ignore=active_model
```
