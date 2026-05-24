# LiMa Reference Project Evaluation

> Updated: 2026-05-23
> Scope: OpenRAG and Google Cloud always-on-memory-agent, evaluated against the current LiMa private coding assistant backend.

## Current LiMa Baseline

LiMa is a private coding assistant backend, not a public RAG platform or commercial model marketplace.

Current reliable request flow:

```text
IDE / terminal agent / private chat
  -> OpenAI or Anthropic compatible endpoint
  -> server.py protocol boundary and access guard
  -> routing_engine.py / router_v3.py / code_orchestrator.py
  -> backend HTTP call and fallback
  -> response quality checks, stats, routing weights, session memory write
```

Current implemented capabilities:

- Private API guard on main `/v1/*` routes.
- Evidence-backed coding backend pools and fallback.
- Request-local context preflight for coding and Anthropic tool paths.
- Session Memory SQLite write path plus compaction trigger after successful responses.
- Tool Gateway registry/executor/audit with `shell=False` command execution and simple argument validation.
- AST scanner, code graph retrieval, reranking, and code-context primitives.
- Routing weights, event log, tracing, guardrails, response pipeline, entity extraction, reflection, ensemble, artifact handles, concurrency pool, and hierarchical memory modules.

Important calibration:

- Some modules are fully in the hot path.
- Some modules are present and tested but not yet driving production behavior.
- Graph retrieval currently computes `_reranked` in `routing_engine.py`, but does not yet inject formatted retrieval context into prompts.
- `context_pipeline.factory.build_default_pipeline()` is covered by tests, but the default pipeline is not the main `server.py` request path.
- `session_memory.processor.session_memory_processor()` can inject memories, but `server.py` currently performs direct memory writes and compaction checks rather than running the processor as the main request context stage.
- `ConcurrencyPool` is implemented and tested, but has not replaced `key_pool.py` or backend key scheduling.

Latest local LiMa target-suite verification:

```text
python -m pytest -q tests .\test_routing_engine.py .\test_rate_limiter.py .\test_http_caller.py .\test_dual_track.py .\test_code_orchestrator.py .\test_streaming.py .\test_skills_injector.py --ignore=active_model
382 passed, 8 skipped
```

Do not describe this as plain full-repo pytest. The workspace contains many local reference repositories, so unrestricted pytest collection can pick up unrelated external tests.

## OpenRAG

Source:

- `https://github.com/langflow-ai/openrag`
- `https://docs.openr.ag/`

OpenRAG is useful to LiMa as a reference for document ingestion, retrieval observability, and MCP-accessible knowledge workflows. It is not a good candidate to replace LiMa's router.

### Useful Ideas

| OpenRAG idea | LiMa value | Recommended LiMa adaptation |
|---|---|---|
| Document ingestion pipeline | High | Build a small `knowledge/` ingestion path for repo docs, markdown, logs, PDFs, and code reports. |
| Docling-style parsing | Medium-high | Use a mature parser for PDFs/Office/HTML instead of custom extraction when LiMa starts ingesting documents. |
| Search/index separation | High | Keep code graph, keyword search, embeddings, and session memory as separable retrieval inputs. |
| Retrieval visibility | High | Add admin retrieval traces showing selected files/chunks/entities and why they were injected. |
| MCP interface | High | Expose LiMa knowledge and memory as tools for IDE/agent clients. |
| Langflow workflows | Low-medium | Borrow the idea of configurable flows; do not add Langflow runtime until LiMa needs visual editing. |
| OpenSearch backend | Low for now | Too heavy for the current personal VPS shape; prefer SQLite FTS5 plus optional local vector index first. |

### What Not To Copy

- Do not turn LiMa into a full public RAG SaaS.
- Do not add OpenSearch as the first knowledge backend unless document scale proves SQLite/FTS insufficient.
- Do not add a Next.js knowledge UI before the admin/retrieval trace path proves useful.
- Do not make Langflow a core dependency for the request path.

### Best Fit For LiMa

OpenRAG should influence LiMa's next knowledge layer:

```text
knowledge/
  ingest.py       # file/doc/report ingestion
  store.py        # SQLite FTS + optional embedding metadata
  retriever.py    # keyword + entity + graph + vector merge
  trace.py        # explain why retrieval results were selected

context_pipeline/
  retrieval_injector.py  # turn retrieval results into prompt context

admin/
  retrieval trace view   # inspect hits, scores, sources, token cost
```

Near-term priority:

1. Turn current `_reranked` graph results into formatted prompt context.
2. Add retrieval trace evidence.
3. Only then evaluate heavier indexing backends.

## Google Cloud Always-On Memory Agent

Source:

- `https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent`

The always-on-memory-agent is more directly relevant to LiMa than OpenRAG because LiMa already has `session_memory`, compaction, routing lessons, status docs, and a need for cross-session continuity.

### Useful Ideas

| Memory-agent idea | LiMa value | Recommended LiMa adaptation |
|---|---|---|
| Always-on background memory process | Very high | Add a lightweight LiMa memory daemon that ingests request logs, docs, progress, and test results outside the hot path. |
| SQLite-first memory store | Very high | Fits LiMa's personal VPS target and existing `session_memory.store`. |
| Inbox ingestion | High | Add `memory_inbox/` or `data/memory_inbox/` for docs, reports, eval outputs, and deployment notes. |
| Ingest / consolidate / query split | Very high | Split raw capture, durable insight generation, and prompt-time recall. |
| Periodic consolidation | Very high | Upgrade compaction from summary-only to insight extraction and contradiction resolution. |
| Memory citations | High | Return memory IDs or source file references in admin traces and future agent recall. |
| No vector DB requirement | High | Keep first implementation simple; add FTS/entity index before a vector database. |

### What Not To Copy

- Do not make Google ADK a hard dependency in LiMa's production router.
- Do not run expensive LLM consolidation synchronously inside `/v1/chat/completions`.
- Do not expose destructive memory endpoints without the same private/admin guard policy.
- Do not store only free-text memories; coding assistant memory needs typed facts.

### Best Fit For LiMa

The better LiMa shape is:

```text
session_memory/
  store.py          # existing SQLite store, extended with typed memory fields
  ingest.py         # convert events/docs/reports into raw memory records
  daemon.py         # periodic inbox processing and consolidation
  query.py          # recall by project, file, topic, backend, and task
  compactor.py      # upgrade to durable insight consolidation

data/
  memory_inbox/     # markdown, json, eval output, deployment notes
```

Suggested memory kinds:

- `user_pref`
- `project_fact`
- `code_fact`
- `ops_event`
- `test_result`
- `routing_lesson`
- `security_lesson`
- `reference_pattern`

Near-term priority:

1. Feed selected docs/reports into `data/memory_inbox/` as source-backed memories.
2. Recall only small cited memory summaries into prompts.
3. Keep long consolidation async and auditable.

## Updated Ranking

| Project | Reference value | Reason |
|---|---:|---|
| Google Cloud always-on-memory-agent | 8.5/10 | Directly matches LiMa's next step: long-term memory, consolidation, inbox ingestion, and evidence-backed recall. |
| OpenRAG | 7/10 | Strong reference for knowledge ingestion, retrieval observability, and MCP knowledge access; too heavy to copy wholesale. |

## Recommended Next Architecture Step

Do not choose between RAG and memory as separate products. LiMa should build a small evidence layer:

```text
raw evidence
  -> request logs, tests, docs, deployment records, code graph, eval JSON
  -> ingestion adapters
  -> SQLite-backed evidence store
  -> retrieval + memory query
  -> prompt injection with trace
  -> response/result updates
```

This is the bridge between OpenRAG and always-on-memory-agent:

- OpenRAG contributes the knowledge ingestion and retrieval trace pattern.
- always-on-memory-agent contributes the background consolidation and durable memory pattern.
- LiMa keeps its own router, backend health model, coding tiers, and private-agent API surface.

## Implementation Order

1. Fix current retrieval hot-path gap: inject formatted graph/code retrieval results, not just compute `_reranked`.
2. Add retrieval trace data to responses or admin diagnostics.
3. Harden prompt-time typed memory recall now that it is a first-class `server.py` stage, including typed-memory ranking and admin-visible memory IDs.
4. Add `lima-mcp` tools for `search_repo`, `search_memory`, `get_retrieval_trace`, and `ask_lima`.
5. Only after these prove useful, evaluate Docling and a heavier search backend.
