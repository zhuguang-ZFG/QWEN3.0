# LiMa Reference Implementation Ledger

> Generated: 2026-05-25
> Purpose: Every external reference mapped to concrete LiMa implementation status.
> Statuses: concept | planned | implementing | implemented | gated | blocked |
> evaluating | rejected

## Legend

| Status | Meaning |
|--------|---------|
| concept | Noted, no code yet. May influence future design. |
| planned | Design doc exists, implementation scheduled. |
| implementing | Code in progress, partial tests. |
| implemented | Code complete, tests pass, integrated. |
| gated | Code exists behind feature flag or approval gate. |
| evaluating | Active review or watchlist, not promoted. |
| blocked | Cannot proceed due to external dependency, legal, or cost gate. |
| rejected | Evaluated and intentionally not adopted. |

---

## Routing / Backend / Provider

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| LiteLLM | implemented | backends.py, key_pool.py | backends.py (170+ backends), key_pool.py (SWRR) | tests/test_backend_registry.py (33 tests) |
| Portkey | implemented | budget_manager.py, backend_reputation.py | budget_manager.py (cost_class), backend_reputation.py (failure penalties) | tests/test_budget_manager.py (13 tests) |
| GPT-Load (SWRR) | implemented | key_pool.py | KeyPool.select() SWRR algorithm | tests/test_key_pool.py (14 tests) |
| One Balance | implemented | key_pool.py | 429->minute cooldown, 401->permanent block | tests/test_key_pool.py |
| Ollama | implemented | backends.py | local_coder14b, local_reasoning, local_general etc. | runtime_topology.py |
| vLLM | concept | - | No runtime dependency | - |
| OpenRouter | implemented | backends.py, provider_automation/ | OR_* backends (17+), openrouter.py (catalog parser) | tests/test_provider_automation.py (47 tests) |

## Async / Concurrency

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| httpx | implemented | http_caller.py | Replaced urllib.request entirely | test_http_caller.py (49 tests) |
| aiohttp | rejected | - | httpx chosen instead | - |
| Asyncio patterns | implemented | streaming.py, speculative.py | bridge_stream_async, speculative_call_async | test_streaming.py, test_routing_engine.py |

## Context / RAG / Retrieval

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| LightRAG | implemented | context_pipeline/graph_retrieval.py | CodeGraph, dual_layer_search (no runtime dep) | tests/test_graph_retrieval.py |
| GraphRAG | concept | - | See LightRAG above | - |
| OpenRAG | concept | - | Ingestion patterns noted | - |
| Sirchmunk | concept | - | File-index patterns noted | - |
| tree-sitter | gated | code_context/ast_adapter.py | AstExtractor ABC, get_extractor("rust")->None | tests/test_code_context_index.py |
| Rerankers (AnswerDotAI) | implemented | context_pipeline/reranking.py | rerank_results, format_for_injection | tests/test_graph_retrieval.py |
| FastEmbed | concept | - | Embedding boundary noted | - |
| LlamaIndex | concept | - | Index patterns noted | - |
| LEANN | gated | local_retrieval/leann_adapter.py | is_leann_available()->False by default | tests/test_local_retrieval.py |

## Memory / Session

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| Mem0 | implemented | session_memory/store.py | Memory taxonomy (10 types), promote/delete/export | tests/test_typed_memory.py |
| Letta (MemGPT) | implemented | context_pipeline/hierarchical_memory.py | 5-layer hierarchy (L0-L4) | tests/test_advanced_patterns.py |
| Zep | concept | - | Long-term memory patterns noted | - |
| stash | concept | - | Inbox patterns noted | - |
| hindsight | concept | - | Consolidation patterns noted | - |
| RuVector | concept | - | Adaptive memory patterns noted | - |
| always-on-memory-agent | implemented | session_memory/daemon.py | Inbox ingestion, fact extraction, consolidation | tests/test_memory_daemon_ctl.py |
| GenericAgent pattern | implemented | session_memory/store.py | Promotions with evidence + audit log | integration smoke test |

## Evaluation / Quality

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| Promptfoo | implemented | coding_eval.py, eval_registry.py | CodingCase, grade_response, run_eval, eval registry | tests/test_coding_eval.py (8 tests), tests/test_eval_registry.py |
| DeepEval | concept | - | Conceptual alignment noted | - |
| Ragas | concept | - | Retrieval eval pattern in retrieval_eval.py | tests/test_graph_retrieval.py |
| Guardrails AI | implemented | context_pipeline/guardrails.py | Input guardrails with severity levels | - |
| Instructor | concept | - | Structured output patterns noted | - |

## Observability / Metrics

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| OpenTelemetry | gated | observability/events.py, metrics.py | LiMa-native events + metrics, no OTEL runtime dep | tests/test_observability.py (29 tests) |
| Prometheus | gated | - | Exporter deliberately excluded | - |
| LangFuse | gated | - | Trace patterns adopted, no cloud exporter | - |
| Phoenix | concept | - | Structured output patterns noted | - |

## Agent / Tool Governance

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| OpenAI Agents SDK | implemented | agent_runtime/ | AgentTask, AgentStep, AgentRuntime (dry-run default) | tests/test_agent_runtime.py (26 tests) |
| Google ADK | concept | - | Multi-agent patterns noted | - |
| Agent Governance Toolkit | implemented | tool_gateway/registry.py, agent_runtime/summary_constraints.py | AuthorityClass (8 levels), dangerous flag, risk class, rollback owner, worker summary contract | tests/test_tool_gateway.py, tests/test_worker_summary_constraints.py |
| gstack | implemented | agent_runtime/approval.py | Stage-gated approval, human-in-the-loop | tests/test_approval_gate.py (17 tests) |
| Symphony | concept | - | - | - |
| A2A | concept | - | Task contract reflects A2A fields | - |
| MCP Python SDK | gated | lima_mcp/, lima_mcp/access_plane.py | 8 dev tools, Bearer auth, read-only default, connector owner/allowlist/credential/timeout/audit policy | tests/test_mcp_access_plane.py |

## Sandbox

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| E2B | gated | sandbox/provider.py | SandboxProvider ABC, FakeSandboxProvider default | tests/test_sandbox_provider.py (21 tests) |
| CubeSandbox | concept | - | Comparison noted | - |

## Streaming / Protocol

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| SSE (sse-starlette) | implemented | streaming_events.py | 8 event types, SSE + OpenAI dual format | tests/test_streaming_events.py (19 tests) |
| VidBee SSE | implemented | streaming_events.py | Task progress events pattern | tests/test_streaming_events.py |

## DevOps / CLI / UX

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| Caddy | concept | - | Deployment docs reference | - |
| Piku | concept | - | - | - |
| Nixpacks | concept | - | - | - |
| Rich | concept | - | cli_status.py uses plain text | tests/test_devops_cli.py |
| OpenCode | implemented | edit_protocol.py | SEARCH/REPLACE block format | tests/test_devops_cli.py |
| Aider | implemented | edit_protocol.py | EditBlock, apply_edits, unique-match validation | tests/test_devops_cli.py (22 tests) |

## Data / Research

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| Quelmap | implemented | data_workbench/ | ArtifactManifest, policy, retention, redaction | tests/test_data_workbench.py (20 tests) |
| OpenRAG data patterns | implemented | data_workbench/ | Ingestion policy, schema redaction | tests/test_data_workbench.py |

## Hardware / Device

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| esp32S_XYZ | implementing | device_gateway/, routes/device_gateway.py, device_gateway/protocol_families.py | Motion protocol, WS gateway, Redis HA, protocol-family allowlists | tests/test_device_gateway_routes.py (16 tests), tests/test_device_gateway_protocol_families.py |
| RuView | concept | - | WiFi CSI ambient perception gated | - |
| VoxCPM | concept | - | TTS gated behind consent/model review | - |
| Qwen3-TTS | concept | - | Apache-2.0, gated | - |

## Provider Automation

| Reference | Status | LiMa Subsystem | Implementation Files | Evidence |
|-----------|--------|---------------|---------------------|----------|
| Shadowbroker | concept | provider_automation/ | Catalog delta tracking, watchlist | tests/test_provider_automation.py (47 tests) |
| last30days | concept | research_radar/ | SourceRecord catalog | tests/test_research_radar.py (18 tests) |
| ECC | concept | research_radar/ | SourceRecord tracked | - |
| MiniMind | concept | - | - | - |

---

## Blocked

Items that cannot proceed due to external dependency, legal, privacy, or cost gates.

| Reference | Reason | Gate |
|-----------|--------|------|
| Always-on worker daemon | Safety: needs repo allowlist, runtime budget, stop marker, audit quarantine | Manual production approval |
| Broad MCP connectors | Authority: MCP tools grant real access | Per-connector owner/allowlist/credential/timeout/audit |
| External sandbox providers (E2B) | Security: remote code execution | Data residency, sandbox limits, cost approval |
| Hosted observability (LangFuse/Prometheus) | Privacy: telemetry data leaves VPS | Data residency, redaction, self-hosting eval |
| Vector DB (external) | Complexity: too heavy for personal VPS | Prove SQLite/FTS insufficient first |
| Voice cloning (VoxCPM/Qwen3-TTS) | Consent + privacy + model license | Explicit consent, retention, false-positive policy |
| Messaging bridges (Telegram/cc-connect) | Platform terms + anti-abuse | Cookie/social/proxy account gates |
| Browser scraping (Hyperbrowser) | Platform terms + scraping policy | Explicit account/credential/cost/anti-abuse gates |
| Hardware companion expansion | Safety + consent | U8 smoke complete, per-protocol-family allowlists |

---

## Summary

| Status | Count |
|--------|-------|
| implemented | 25 |
| gated | 7 |
| concept | 29 |
| implementing | 1 |
| evaluating | 0 |
| rejected | 1 |
| blocked | 9 |

## Closed P0 Review Items

1. **Retrieval injection path**: `routing_engine.inject_retrieval_context()` is the single authority; `context_pipeline/processors.py` is quarantined behind `LIMA_CONTEXT_PREFLIGHT=1`.
2. **Memory taxonomy**: `session_memory/store.py` now has canonical memory types, source ids, and export/delete/admin gates.
3. **Observability exporter**: hosted Prometheus/OTEL/LangFuse exporters remain gated; local eval registry evidence is implemented in `eval_registry.py`.
4. **MCP connectors**: `lima_mcp/access_plane.py` records owner, allowlist, credential boundary, timeout, audit, and failure mode before a connector is valid.

## Next Actionable Milestones

| Phase | Scope |
|-------|-------|
| Phase 2 | Closed - code intelligence contracts, trace quality fields, static-analysis lane |
| Phase 3 | Closed - memory taxonomy, source citations, export/delete/redaction gate |
| Phase 4 | Closed - risk class, approval requirement per authority, tool audit provenance |
| Phase 5 | Closed - read-only MCP access plane with owner/allowlist/credential/timeout/audit |
| Phase 6 | Closed - unified eval registry with scores, promotion, costs, fail reasons |
| Phase 7 | LiMa Code UX - stage-gated commands (plan/review/test/ship), review-context prefetch |
| Phase 8 | Closed - protocol families separated; non-motion families gated |
