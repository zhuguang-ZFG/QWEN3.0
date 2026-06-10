# LiMa 10 Subsystem Open Source Recommendations

> Date: 2026-05-24
> Scope: de-duplicated enhancement radar for LiMa Server, Agent Worker,
> `tool_gateway`, `context_pipeline`, `session_memory`, `quality_gate`,
> monitoring, governance, protocol, deployment, and terminal UX work.

## Rules

- This is a planning radar, not an install list.
- Keep the existing LiMa-owned APIs, provider/key custody, audit records, and
  human approval gates authoritative.
- Treat existing radar projects as strengthened references rather than duplicate
  adoption paths.
- Before any runtime dependency is introduced, run a per-project license,
  security, maintenance, secret, network, data-retention, and rollback review.
- GPL, AGPL, LGPL, source-available, mixed-license, archived, unresolved, or
  no-SPDX projects remain concept-only unless separately isolated.

## Source Check Notes

- Checked with GitHub API, raw license files, or `git ls-remote` on
  2026-05-24 where possible.
- `LiteLLM` and `LangFuse` expose mixed license files through raw `LICENSE`;
  do not treat them as plain MIT runtime dependencies without package-level
  review.
- `Arize Phoenix` raw license is Elastic License 2.0.
- `sourcegraph/cody` returned repository-not-found for the supplied path during
  this review; keep Sourcegraph Cody ideas concept-only until the current source
  repository is confirmed.
- `braintrustdata/braintrust` returned repository-not-found for the supplied
  path during this review; `braintrustdata/braintrust-sdk-python` has
  Apache-2.0, but the product/source boundary needs a separate check.
- `protectai/rebuff` is archived; use only as a historical prompt-injection
  detection reference.

## 1. Coding Worker And Agent Execution

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `openai/openai-agents-python` | MIT | P0 | Existing radar item. Borrow agent/tool/guardrail/handoff/session/tracing vocabulary for `agent_tasks` and `tool_gateway`. | Keep LiMa provider custody and audit schema authoritative. |
| `google/adk-python` | Apache-2.0 | P0 | Existing radar item. Borrow code-first agent app shape, eval/deploy separation, and workflow state boundaries. | No hard dependency in router until adapter tests exist. |
| `TencentCloud/CubeSandbox` | No SPDX / license file not found in raw check | P0 | Existing radar item. Evaluate as isolated worker execution provider for untrusted code. | License, deployment, network, cost, data egress, and cleanup review first. |
| `e2b-dev/e2b` | Apache-2.0 | P0 | New candidate. Compare with CubeSandbox as a mature agent sandbox/environment provider. | Default-off; secrets/network/filesystem boundaries and cost controls required. |
| `openai/symphony` | Apache-2.0 | P1 | Existing radar item. Borrow isolated work runs, proof bundles, CI/PR evidence. | Must not bypass review, push, deploy, or hardware gates. |
| `garrytan/gstack` | MIT | P1 | Existing radar item. Borrow stage-gated plan/review/QA/security/ship workflow. | Avoid role sprawl and broad skill auto-install. |
| `addyosmani/agent-skills` | MIT | P1 | Existing radar item. Borrow skill packaging and quality-gate vocabulary. | Skills remain methods, not permissions. |

## 2. Backend Routing And Load Balancing

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `BerriAI/litellm` | Mixed license file / no SPDX in API | P0 | Strengthens existing LiMa routing notes. Borrow provider abstraction, fallback, cost tracking, and rate-limit patterns. | Do not replace LiMa router wholesale; review mixed license and enterprise paths. |
| `Portkey-AI/gateway` | MIT | P0 | Strengthens existing routing notes. Borrow AI gateway rules, retries, fallback, caching, canary, and guardrail placement. | Keep LiMa backend registry and key custody authoritative. |
| `ollama/ollama` | MIT | P1 | Strengthens local model route. Borrow local model lifecycle, concurrency, GPU/layer, and batch controls. | Local-only by default; resource caps and model admission required. |
| `vllm-project/vllm` | Apache-2.0 | P1 | Future self-hosted inference backend for throughput, continuous batching, and OpenAI-compatible serving. | Linux/GPU serving plan, memory budget, and admission tests required. |
| `aio-libs/aiohttp` | Apache-2.0 | P1 | Candidate for true async provider calls if `http_caller.py` moves beyond sync urllib. | Only after async contract, timeout, cancellation, and key-pool concurrency tests. |

## 3. Context Engineering And RAG

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `HKUDS/LightRAG` | MIT | P0 | Existing radar item. Borrow graph/vector retrieval and multimodal parsing boundaries. | Adapter behind LiMa `context_pipeline` interface. |
| `microsoft/graphrag` | MIT | P0 | New candidate. Borrow entity extraction, community detection, and hierarchical summaries for repo/code understanding. | Benchmark against LiMa data before storage/index changes. |
| `AnswerDotAI/rerankers` | Apache-2.0 | P0 | New candidate. Standardize reranker abstraction for local and hosted rerankers. | Provider/model terms and latency/cost baselines required. |
| `tree-sitter/tree-sitter` | MIT | P0 | New candidate. Use AST-level parsing for future code scanning and repo map quality. | Language grammar review and fallback to text scanning. |
| `run-llama/llama_index` | MIT | P1 | New candidate. Borrow ingestion pipeline and query-engine abstraction. | Avoid framework rewrite; adopt only small interface ideas first. |
| `qdrant/fastembed` | Apache-2.0 | P1 | New candidate. Lightweight local embedding for VPS/local RAG. | Model download, retention, CPU/RAM, and rebuild policy required. |
| Sourcegraph Cody | Current repo path unresolved | P1 | Concept-only for codebase search and prompt context construction. | Confirm source repository/license before reuse. |

## 4. Memory System

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `mem0ai/mem0` | Apache-2.0 | P0 | New candidate. Borrow long-term/user/session memory taxonomy and vector retrieval interface. | Privacy, consent, deletion, secret redaction, and promotion evidence required. |
| `letta-ai/letta` | Apache-2.0 | P0 | New candidate. Borrow stateful-agent memory and self-editing memory vocabulary. | No autonomous memory mutation without promotion/rejection audit. |
| `memodb-io/memobase` | Apache-2.0 | P1 | New candidate. Borrow profile plus event-timeline structure for user model. | Explicit user consent and profile export/delete required. |
| `getzep/zep` | Apache-2.0 | P1 | New candidate. Borrow conversation memory, graph memory, vector search, and summarization strategy. | Keep LiMa storage and retention policy authoritative. |

## 5. Evaluation And Quality Assurance

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `promptfoo/promptfoo` | MIT | P0 | New candidate. Declarative prompt/agent/RAG tests, red-team checks, model comparisons. | Do not send private prompts/data to external providers by default. |
| `confident-ai/deepeval` | Apache-2.0 | P0 | New candidate. Borrow metric vocabulary for correctness, faithfulness, relevance, toxicity, and bias. | Golden datasets and deterministic fixtures before gating releases. |
| `langfuse/langfuse` | Mixed license file / no SPDX in API | P0 | New candidate. LLM tracing, prompt management, eval datasets, playground, and cost views. | Mixed license, data residency, self-hosting, and trace redaction review. |
| `explodinggradients/ragas` | Apache-2.0 | P1 | New candidate. RAG-specific metrics for retrieval quality and faithfulness. | Requires stable retrieval fixtures and source-grounded expected answers. |
| `instructor-ai/instructor` | MIT | P1 | New candidate. Structured output validation with Pydantic-style schemas. | Use to validate boundaries; do not hide model errors. |
| Braintrust | Supplied repo unresolved; SDK Apache-2.0 found | P2 | Concept-only for eval/log/data management until current source is confirmed. | Confirm repository, license, hosting, and data flow. |

## 6. Observability And Monitoring

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `open-telemetry/opentelemetry-python` | Apache-2.0 | P0 | New candidate. Standard traces, metrics, and logs for `health_tracker`, `probe_loop`, router, and workers. | Redact prompts, keys, dataset names, and user content by default. |
| `prometheus/client_python` | Apache-2.0 | P0 | New candidate. Export LiMa health, cooldown, latency, quality, and key-pool metrics. | No secrets or raw prompts in labels. |
| `Arize-ai/phoenix` | Elastic-2.0 | P1 | New candidate. LLM/RAG observability and retrieval analysis. | ELv2 review and self-hosted data-retention policy. |
| `mlflow/mlflow` | Apache-2.0 | P2 | New candidate. Future experiment tracking/model registry if LiMa trains or fine-tunes models. | Only after model training/eval lane exists. |

## 7. Security And Governance

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `microsoft/agent-governance-toolkit` | MIT | P0 | Existing radar item. Borrow risk classes, approval metadata, audit fields, policy templates. | Policy must be enforced in LiMa task/tool gates. |
| `guardrails-ai/guardrails` | Apache-2.0 | P0 | New candidate. Output validation and custom validators for model/tool responses. | Use as validation layer, not a substitute for app-side checks. |
| `protectai/llm-guard` | MIT | P1 | New candidate. Prompt injection, PII, toxicity, and unsafe-content scanning. | Measure false positives and never silently drop user intent. |
| `protectai/rebuff` | Apache-2.0; archived | P1 | Historical prompt-injection detector reference. | Concept-only due archived status. |
| `semgrep/semgrep` | LGPL-2.1 | P1 | Existing MCP catalog concept. Use SAST before risky code execution or release. | LGPL isolation, local-only scans, and rule provenance required. |

## 8. Streaming And Protocol Enhancement

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `modelcontextprotocol/python-sdk` | MIT | P0 | New candidate. Official MCP Python SDK for standard tool servers/clients. | Tool permissions, credential custody, audit, and allowlists remain LiMa-owned. |
| `sysid/sse-starlette` | BSD-3-Clause | P1 | New candidate. Cleaner FastAPI SSE streaming for chat/tool progress. | Backpressure, disconnect, cancellation, timeout, and auth tests required. |
| `google/A2A` | Apache-2.0 | P1 | New candidate. Agent-to-agent task protocol for future LiMa Server to Agent Worker contracts. | Do not replace current contract until schema parity and security gates exist. |

## 9. Infrastructure And DevOps

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `caddyserver/caddy` | Apache-2.0 | P1 | New candidate. Simplify VPS reverse proxy and automatic HTTPS. | Staging deployment, rollback, TLS ownership, and port policy required. |
| `piku/piku` | MIT | P1 | New candidate. Minimal git-push deployment model for personal VPS scale. | Compare against current systemd/rsync flow; no auto-deploy without approval. |
| `railwayapp/nixpacks` | MIT | P1 | New candidate. Reproducible app builds and dependency detection. | Build reproducibility and China/VPS mirror behavior must be tested. |
| `dagger/dagger` | Apache-2.0 | P2 | New candidate. Pipeline-as-code for build/test/deploy automation. | Only after current deployment scripts stabilize. |

## 10. Terminal UI And Developer Experience

| Project | License signal | Priority | LiMa adaptation | Gate |
|---|---|---:|---|---|
| `Textualize/rich` | MIT | P1 | New candidate. Better CLI tables, panels, progress, markdown rendering. | Keep output plain-text compatible and log-safe. |
| `paul-gauthier/aider` | Apache-2.0 | P1 | Existing local docs reference. Borrow SEARCH/REPLACE editing, repo map, weak/strong model split. | Do not import agent behavior wholesale; Agent Worker remains executor. |
| `Textualize/textual` | MIT | P2 | New candidate. Future TUI panels and local developer dashboard. | Defer until CLI contracts stabilize. |
| `OpenInterpreter/open-interpreter` | AGPL-3.0 | P2 | Concept-only natural-language computer API reference. | AGPL isolation; no code copy or runtime dependency. |

## First Closed-Loop Slices

1. Router and provider layer:
   - compare LiMa's current backend registry against LiteLLM and Portkey
     patterns;
   - add missing fallback/rate-limit/cost telemetry ideas without replacing
     LiMa's key custody.
2. Worker safety:
   - evaluate E2B and CubeSandbox through a no-secret, disposable fixture;
   - record filesystem, network, timeout, cleanup, and cost boundaries.
3. Context quality:
   - add a reranker interface inspired by `rerankers`;
   - prototype `tree-sitter` AST extraction behind a feature flag.
4. Memory:
   - map Mem0/Letta/Zep/Memobase concepts to LiMa memory record types;
   - add delete/export/secret-redaction gates before persistence expansion.
5. Evaluation and observability:
   - define a promptfoo/deepeval/ragas-compatible fixture shape;
   - add OpenTelemetry/Prometheus metrics names before adding exporters.
6. Protocol:
   - plan MCP Python SDK compatibility for read-only tools first;
   - keep A2A as a future task-contract reference.
7. DevOps and UX:
   - evaluate Caddy/Nixpacks/Piku as deployment simplifiers only after current
     VPS flow is fully documented;
   - improve CLI rendering with Rich only where logs remain parseable.

## Non-Goals

- No mass dependency installation.
- No framework rewrite.
- No automatic cloud provider, database, browser, messaging, deployment, or
  hardware permission expansion.
- No private prompt, dataset, schema, trace, or source-code export to hosted
  observability/eval services without explicit consent and redaction.
