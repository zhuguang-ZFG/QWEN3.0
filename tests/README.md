# LiMa 测试套件索引

> 更新：2026-06-15 | `tests/` 下约 230+ 测试文件（扁平布局；本文件为所有权索引）

## 运行方式

### 聚焦门（本地提交 / 里程碑 closeout 默认）

快速预提交（ruff + staged py_compile，**不跑全量 pytest**）：

```powershell
python scripts/run_pre_commit_check.py
```

常用**领域聚焦** pytest（改动相关模块时优先）：

```powershell
# 路由权威边界
python -m pytest tests/test_routing_pipeline_authority.py tests/test_routing_engine.py tests/test_route_scorer.py -q

# 设备网关 + memory/ledger
python -m pytest tests/test_device_gateway_store.py tests/test_device_memory_*.py tests/test_device_store_redis_backends.py -q

# Channel gateway
python -m pytest tests/test_channel_gateway_service.py tests/test_channel_branding_media.py tests/test_channel_keyword_voice_ux.py -q

# Provider automation（拆分后四文件）
python -m pytest tests/test_provider_automation_catalog.py tests/test_provider_automation_runner.py tests/test_provider_automation_impact.py tests/test_provider_automation_admission.py -q

# Ops metrics（拆分后四文件）
python -m pytest tests/test_ops_metrics_core.py tests/test_ops_metrics_eval.py tests/test_ops_metrics_payload.py tests/test_ops_metrics_backends.py -q
```

### 全量门（CI 风格 / 发布前）

```powershell
python scripts/run_pre_commit_check.py --full
```

等价于带长期/外部依赖忽略的完整 pytest（见 `scripts/run_pre_commit_check.py` 中 `CI_PYTEST_IGNORES`）。

其他常用全量变体：

```powershell
python -m pytest -q --ignore=tests/test_ci_gates.py
python -m pytest tests -q --ignore=tests/test_memory_daemon_ctl.py --ignore=tests/test_semantic_code_retrieval.py
```

### 何时用哪个门

| 场景 | 推荐 |
|------|------|
| 日常小改、单切片 closeout | 聚焦 pytest + `run_pre_commit_check.py` |
| 触及路由/设备/ops 热路径 | 上表对应领域命令 |
| 里程碑发布、VPS 部署前 | `--full` 全量门 |
| P13 / ruff / py_compile | 预提交脚本默认包含 |

## 共享测试辅助模块

| 文件 | 用途 |
|------|------|
| `tests/provider_automation_helpers.py` | `entry()` 工厂（provider_automation 测试） |
| `tests/ops_metrics_helpers.py` | `reload_prometheus_metrics()` |

`tests/conftest.py` 将 `tests/` 加入 `sys.path`，支持 `from provider_automation_helpers import ...`。

## Ownership Map

### Request Pipeline
- `test_routing_engine.py` — 5-layer routing
- `test_routing_pipeline_authority.py` — **module ownership matrix** (16 boundary tests)
- `test_route_scorer.py` — quality/stability/latency scoring
- `test_route_post_process.py` — post-route hooks
- `test_request_context_preflight.py` — preflight contracts
- `test_http_caller.py` / `test_http_caller_concurrency.py` — backend transport
- `test_http_body_limit.py` — ASGI body limit
- `test_router_circuit_breaker.py` — health/cooldown
- `test_router_classifier.py` — `routing_intent.analyze_intent()` classification
- `test_routing_weights.py` / `test_routing_weights_persistence.py` — weight learning
- `test_routing_loop.py` — closed-loop feedback
- `test_routing_ml.py` — ML routing model
- Root: `test_http_caller.py`, `test_rate_limiter.py`, `test_streaming.py`

### Response & Quality
- `test_response_pipeline.py` — processor chain
- `test_code_validation_processor.py` — code syntax + security
- `test_response_validator.py` — ast.parse + patterns
- `test_quality_gate.py` — text quality
- `test_response_cleaner_identity.py` — identity leak cleaning
- `test_stream_footer.py` / `test_streaming_events.py` — SSE streaming

### Chat & Protocol
- `test_chat_endpoints.py` / `test_chat_handler.py`
- `test_chat_fallback.py` / `test_chat_models.py` / `test_chat_request_utils.py`
- `test_chat_ide_golden_path.py` — IDE golden path
- `test_anthropic_tool_protocol.py` / `test_anthropic_format_tools.py` / `test_anthropic_preflight.py`
- `test_tool_forward.py` / `test_tool_forward_failures.py`
- `test_tool_gateway.py` / `test_tool_gateway_adapter.py`
- `test_ide_detection.py` / `test_vision_routing.py`
- `test_system_endpoints.py` — /v1/models, /health, /api/live-key

### Code Context & Retrieval
- `test_lima_context.py` — context preflight
- `test_code_context_index.py` — AST + graph
- `test_retrieval_injection.py` / `test_production_retrieval.py`
- `test_graph_retrieval.py` / `test_local_retrieval.py`
- `test_context_cache.py` — semantic cache
- `test_context_pipeline.py` — pipeline stages
- `test_complexity.py` / `test_compactor.py`
- `test_multilang_context.py` — multi-language context
- `test_phase_b.py` — auto-indexer
- `test_reranker_protocol.py` — reranker

### Session Memory & Learning
- `test_session_memory.py` / `test_typed_memory.py`
- `test_learning_loop.py` — four-channel learning
- `test_prompt_memory_recall.py` — prompt-time recall
- `test_mastery_loop.py` — module mastery
- `test_memory_daemon_ctl.py` — daemon control

### Agent Runtime & Evolution
- `test_agent_runtime.py` / `test_agent_orchestrator.py`
- `test_agent_store.py` / `test_agent_roles.py`
- `test_agent_task_routes.py` / `test_agent_task_contract.py`
- `test_agent_eval.py` / `test_agent_evolution.py`
- `test_real_execution.py` / `test_real_executor.py`
- `test_safe_execution.py` / `test_safe_math.py`
- `test_artifact.py` / `test_prompt_contract.py`
- `test_approval_gate.py` / `test_learning_loop.py`
- `test_module_split_imports.py` — module split compat

### Device Gateway & ESP32
- `test_device_gateway_routes.py` / `test_device_gateway_protocol.py`
- `test_device_gateway_store.py` / `test_device_gateway_redis_store.py`
- `test_device_gateway_concurrency.py`
- `test_device_gateway_motion_contract.py` / `test_device_motion.py`
- `test_device_gateway_path_pipeline.py` / `test_device_gateway_path_validator.py`
- `test_device_gateway_protocol_families.py`
- `test_p1_4_device_stability_gate.py`

### Channel Gateway
- `test_channel_gateway_routes.py` / `test_channel_gateway_service.py`
- `test_channel_gateway_store.py` / `test_channel_gateway_commands.py`
- `test_channel_gateway_integrations.py`
- `test_channel_branding_media.py` / `test_channel_chat_session.py`
- `test_channel_keyword_voice_ux.py` / `test_channel_public_apis.py` / `test_channel_tools.py`

### Retired Channels
- Telegram bot/operator tests were removed in the 2026-06-09 retirement slice.
- `test_channel_retirement.py` proves `/telegram` routes are no longer registered.

### Security & Auth
- `test_access_guard.py` / `test_identity_hardening.py`
- `test_secret_hygiene.py` / `test_repo_hygiene.py`
- `test_admin_csrf.py` / `test_admin_paths.py` / `test_admin_ui.py`
- `test_admin_stats.py` / `test_admin_agent_audit.py`
- `test_user_identity.py` / `test_embeddings_guard.py`
- `test_image_endpoint_guard.py` / `test_zerokey_endpoints.py`

### Backend Evaluation & Registry
- `test_free_web_ai_probe.py` / `test_free_web_ai_admission.py`
- `test_backend_registry.py` / `test_backend_admission_overlay.py` / `test_backend_reputation.py`
- `test_budget_manager.py` / `test_budget_cf_google.py` / `test_key_pool.py`
- `test_backends_registry_utils.py`

> 注：`test_coding_eval.py`、`test_eval_*.py`、`test_periodic_coding_eval.py`、`test_web_reverse_eval.py` 等编码评测测试已随编码能力退役（2026-06-26）物理删除。

### MCP & External Tools
- `test_mcp_registries.py` / `test_mcp_tools.py`
- `test_cloudflare_adapter.py` / `test_codesearch_adapter.py`
- `test_gitee_ai_adapter.py` / `test_search_gateway.py`
- `test_lima_code_dev_search_tools.py`

> 注：`test_mcp_access_plane.py` 已随 `lima_mcp/` HTTP 路由退役删除。

### Observability & Ops
- `test_ops_metrics_core.py` / `test_ops_metrics_eval.py` / `test_ops_metrics_payload.py` / `test_ops_metrics_backends.py`（原 `test_ops_metrics.py` 拆分）
- `test_ops_alerts.py` / `test_ops_entrypoint.py`
- `test_observability.py` / `test_capability_evidence.py`
- `test_event_log.py` / `test_request_stats.py`
- `test_healthchecks_io.py` / `test_healthcheck_ping.py` / `test_health_summary.py`

### CI & Infrastructure
- `test_ci_gates.py` — ruff/pyright/deptry enforcement
- `test_hypothesis_*.py` — property-based tests (4 files)
- `test_deploy_common.py` / `test_deploy_v3_security.py`
- `test_repo_manifest.py` / `test_five_line_closeout.py`

### Research & External Integrations
- `test_research.py` / `test_research_radar.py`
- `test_gitee_ai_adapter.py` — Gitee 模力方舟 AI 后端（注意：Gitee 镜像同步相关脚本与测试已归档至 `docs/archive/retired/`）
- `test_local_tool_modules.py`
- `test_provider_inventory.py` / `test_provider_automation_catalog.py` / `test_provider_automation_runner.py` / `test_provider_automation_impact.py` / `test_provider_automation_admission.py`
- `test_narrative.py` / `test_lightrag.py`

### Misc / Cross-cutting
- `test_advanced_patterns.py` / `test_ensemble.py`
- `test_data_workbench.py` / `test_devops_cli.py`
- `test_phase19_22.py` / `test_phase26_28.py`
- `test_pipeline_integration.py` / `test_fleet.py`
- `test_oldllm_diag.py` / `test_oldllm_sync.py`
- `test_public_apis_60s.py` / `test_public_apis_lookup.py`
- `test_sandbox_provider.py` / `test_static_analysis.py`
- `test_tinyfish_transport_safety.py` / `test_worker_summary_constraints.py`
- `test_e2e_release.py` / `test_mimo_stt.py` / `test_apprise_bridge.py`
- `test_lima_smoke_task_script.py`
