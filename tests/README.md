# LiMa Test Suite Map

> Updated: 2026-06-07 | 279 test files, ~3000+ test cases
> Filenames stay flat under `tests/`; this file is the ownership index.

## Running

```powershell
python -m pytest -q --ignore=tests/test_ci_gates.py
```

Focused slice:
```powershell
python -m pytest tests/test_routing_engine.py tests/test_http_caller.py -q
```

## Ownership Map

### Request Pipeline
- `test_routing_engine.py` — 5-layer routing + backend-aware skill reinjection
- `test_skills_injector.py` — skill prompt injection & marker-based deduplication
- `test_route_scorer.py` — quality/stability/latency scoring
- `test_route_post_process.py` — post-route hooks
- `test_request_pipeline_authority.py` — module ownership matrix
- `test_request_context_preflight.py` — preflight contracts
- `test_http_caller.py` / `test_http_caller_concurrency.py` — backend transport
- `test_http_body_limit.py` — ASGI body limit
- `test_router_circuit_breaker.py` — health/cooldown
- `test_router_classifier.py` — intent classification
- `test_routing_weights.py` / `test_routing_weights_persistence.py` — weight learning
- `test_dual_track.py` — smart_router migration tracking
- `test_health_tracker.py` — backend health monitoring
- `test_budget_manager.py` — token budget & CF/Google facade
- `test_coding_pool_admission.py` — IDE coder pool evidence gate

### Response & Quality
- `test_response_pipeline.py` — processor chain
- `test_code_validation_processor.py` — code syntax + security
- `test_response_validator.py` — ast.parse + patterns
- `test_quality_gate.py` — text quality
- `test_response_cleaner_identity.py` — identity leak cleaning

### Chat & Protocol
- `test_chat_endpoints.py` / `test_chat_handler.py` / `test_chat_handler_dispatch.py`
- `test_chat_ide_golden_path.py` — IDE detection & OpenCode E2E golden path
- `test_anthropic_tool_protocol.py` / `test_anthropic_format_tools.py`
- `test_anthropic_preflight.py` — Anthropic request validation
- `test_tool_forward.py` / `test_tool_forward_failures.py`
- `test_ide_detection.py` / `test_vision_routing.py`
- `test_opencode_e2e.py` / `test_opencode_e2e_cases.py` — OpenCode integration tests

### Code Context & Retrieval
- `test_lima_context.py` — context preflight
- `test_code_context_index.py` — AST + graph
- `test_retrieval_injection.py` / `test_production_retrieval.py`
- `test_graph_retrieval.py` / `test_local_retrieval.py`
- `test_context_cache.py` — semantic cache
- `test_phase_b.py` — auto-indexer

### Session Memory & Learning
- `test_session_memory.py` / `test_typed_memory.py`
- `test_learning_loop.py` — four-channel learning
- `test_prompt_memory_recall.py` — prompt-time recall
- `test_mastery_loop.py` — module mastery

### Agent Runtime
- `test_agent_runtime.py` / `test_agent_orchestrator.py`
- `test_agent_store.py` / `test_agent_task_routes.py`
- `test_real_execution.py` / `test_real_executor.py`
- `test_artifact.py` / `test_prompt_contract.py`

### Device Gateway
- `test_device_gateway_routes.py` / `test_device_gateway_protocol.py`
- `test_device_gateway_store.py` / `test_device_gateway_redis_store.py`
- `test_device_gateway_concurrency.py`
- `test_device_gateway_motion_contract.py` / `test_device_motion.py`

### Channel Gateway
- `test_channel_gateway_routes.py` / `test_channel_gateway_service.py`
- `test_channel_gateway_store.py` / `test_channel_gateway_commands.py`
- `test_channel_gateway_integrations.py`

### Telegram (17 files)
- `test_telegram_bot.py` / `test_telegram_dispatch.py` / `test_telegram_inline.py`
- `test_telegram_dev_skills.py` / `test_telegram_diag_tools.py`
- `test_telegram_outbound.py` / `test_telegram_digest.py`
- etc.

### Security & Hygiene
- `test_access_guard.py` / `test_identity_hardening.py`
- `test_secret_hygiene.py` / `test_repo_hygiene.py`
- `test_admin_csrf.py` / `test_admin_paths.py`

### Backend Evaluation
- `test_coding_eval.py` / `test_free_web_ai_probe.py`
- `test_free_web_ai_admission.py` / `test_backend_registry.py`

### CI & Infrastructure
- `test_ci_gates.py` — ruff/pyright/deptry enforcement
- `test_hypothesis_*.py` — property-based tests (routing, security, APIs)
- `test_deploy_common.py` / `test_deploy_v3_security.py`
