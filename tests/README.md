# LiMa Tests

Flat layout: all files stay `tests/test_*.py` (no mass move). Use this map for ownership.

## Request protocol and HTTP

- `test_http_body_limit.py`, `test_chat_endpoints.py`, `test_chat_handler.py`
- `test_chat_models.py`, `test_chat_request_utils.py`, `test_access_guard.py`
- `test_anthropic_*`, `test_tool_forward*.py`, `test_stream_*`

## Routing and backends

- `test_routing_engine.py`, `test_router_*.py`, `test_chat_fallback.py`
- `test_code_orchestrator_routing.py`, `test_backend_registry.py`
- `test_health_tracker.py`, `test_key_pool.py`, `test_budget_manager.py`

## Device gateway and ESP32 contract

- `test_device_gateway_*.py`, `test_device_motion.py`, `test_p1_4_device_stability_gate.py`

## Agent runtime and tasks

- `test_agent_orchestrator.py`, `test_agent_runtime.py`, `test_agent_store.py`
- `test_agent_task_*.py`, `test_agent_evolution.py`, `test_approval_gate.py`
- `test_real_executor.py`, `test_tool_gateway*.py`

## Memory and retrieval

- `test_prompt_memory_recall.py`, `test_retrieval_*.py`, `test_local_retrieval.py`
- `test_context_pipeline.py`, `test_context_cache.py`, `test_semantic_cache.py`
- `test_learning_loop.py`, `test_typed_memory.py`

## Ops, security, hygiene

- `test_secret_hygiene.py`, `test_repo_hygiene.py`, `test_ops_metrics.py`
- `test_admin_*.py`, `test_system_endpoints.py`, `test_identity_hardening.py`

## Channel / Telegram / WeChat

- `test_telegram_*.py`, `test_channel_gateway_*.py`, `test_wechat_channel_smoke.py`

## Provider automation and eval

- `test_provider_automation.py`, `test_web_reverse_eval.py`, `test_eval_registry.py`

## Running

```powershell
python -m pytest tests/test_quality_gate.py tests/test_http_body_limit.py -q
python -m pytest
```
