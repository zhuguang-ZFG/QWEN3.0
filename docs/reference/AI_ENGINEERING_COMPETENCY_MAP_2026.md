# AI Engineering Competency Map 2026

> Updated: 2026-05-25
> Source type: user-provided 2026 AI engineer interview / production AI map.
> Scope: map the 12 concepts to LiMa Server, LiMa Code, and future hardware
> control work.

## Purpose

This document turns the 12 interview concepts into LiMa engineering gates. The
point is not interview prep by itself; it is a production checklist for model
routing, coding agents, memory, retrieval, evaluation, cost control, and
deployment.

## Competency Table

| Concept | LiMa interpretation | Current LiMa state | Next gate |
|---|---|---|---|
| Prompt engineering | Prompt templates, task contracts, context preflight, tool instructions, identity handling, and prompt-injection defense. | Server prompt staging, IDE/source hints, context digest, LiMa Code task prompts, and prompt tests exist. | Make prompt contracts versioned data with regression snapshots for high-risk routes. |
| RAG | Knowledge is decoupled from model weights; retrieval trace quality limits answer quality. | Code/document retrieval, reranking, prompt injection, and MCP/admin retrieval traces exist. | Keep one authoritative retrieval injection path and add stronger source-quality scoring. |
| Vector embeddings and databases | Semantic search is a storage/indexing problem, not just a model call. | LiMa has local code-context/index boundaries and semantic-cache data, but no required production vector DB. | Add a swappable graph/vector index interface before choosing PGVector, Qdrant, or another store. |
| Agentic AI and tool calling | Agents are bounded workers with tools, ownership, evidence, and stop gates. | LiMa Code worker, MCP tools, Device Gateway tasks, and sub-agent governance are documented. | Add per-tool risk class, approval metadata, and audit events before broad tool expansion. |
| Reasoning and deliberation | Expensive reasoning is an explicit mode with cost/latency tradeoffs, not a hidden default. | Routing distinguishes reasoning/coding tiers and records backend evidence. | Add task-level reasoning budget policies and summarized reasoning evidence, not raw hidden chain-of-thought storage. |
| Memory management | Long-running AI needs typed short-term/long-term memory, compaction, recall, and promotion gates. | SQLite session memory, daemon compaction, prompt-time recall, and memory promotion rules exist. | Add memory IDs/citations to more admin traces and worker recall outputs. |
| Streaming and async | User experience and throughput depend on streaming, async tool work, and background jobs. | OpenAI/Anthropic streaming paths, async backends, background memory daemon, agent task store, and Redis-backed Device Gateway WebSocket task routing exist. | Expand async observability around tool calls, stream footers, Redis queue depth, and device in-flight tasks. |
| Inference optimization | Cost and latency improve through model routing, caching, topology awareness, and local/proxy backends. | Backend scoring, health tracking, topology guard, SCNet/Cloudflare/local proxy routing, and fallback windows exist. | Add more formal cache hit/miss and p50/p95 cost-latency reports by route class. |
| Token and cost management | FinOps is prompt compression, model routing, quotas, budgets, and telemetry. | Token-safe refresh, context budget checks, route scoring, quota-state handling, and provider key custody exist. | Add per-task budget envelopes and cost attribution to LiMa Code worker runs. |
| Fine-tuning and PEFT | Fine-tuning should align style/task format, not serve as a knowledge database. | LiMa currently prefers routing, prompts, RAG, memory, and adapters over training. | Keep fine-tuning gated until eval data, privacy, retention, and rollback are ready. |
| LLM evaluation | Production AI needs repeatable fixtures, judge policies, golden cases, and CI-style evidence. | Coding backend evals, smoke reports, route admission, mastery loop, and pytest gates exist. | Add a unified eval registry that links model, route, fixture, score, and promotion decision. |
| MLOps and deployment | Reliability comes from guardrails, monitoring, drift checks, rollback, and deployment evidence. | VPS deployment records, health checks, nginx/security notes, docs status, Device Gateway Redis HA deployment, and GitHub push discipline exist. | Add drift/regression dashboards and a separate worker-count rollout before multi-machine production. |

## LiMa Operating Rules

- Prefer engineering controls over prompt-only controls.
- Keep knowledge in retrieval/memory stores, not fine-tuned weights, unless a
  separate privacy/eval/license review approves training.
- Treat tools and hardware commands as authority-bearing actions with
  allowlists, audit, approval, timeout, and rollback.
- Measure before promotion: every backend, prompt contract, tool, memory rule,
  and deployment path needs repeatable evidence.
- Optimize cost and latency through routing, caching, streaming, and budgets
  before adding larger models.
- Never store raw secrets, private keys, raw chain-of-thought, or unreviewed
  personal training data as memory.

## Project Fit

| Repo | Competency focus |
|---|---|
| Main LiMa repo | Routing, RAG, memory, evals, FinOps, MLOps, Device Gateway safety. |
| `deepcode-cli` / LiMa Code | Prompt contracts, tool calling, local worker UX, MCP connector discipline, coding eval evidence. |
| `esp32S_XYZ` | Tool/hardware safety, async device control, command schemas, fake/real device verification. |

## Implementation Order

1. Keep prompt/RAG/memory/eval evidence stable.
2. Add unified eval registry and per-task budget envelopes.
3. Add MCP/tool risk metadata to agent tasks.
4. Add graph/vector index abstraction before introducing a production vector DB.
5. Add drift/cost/latency dashboards before increasing worker count or moving from single-VPS Redis HA to multi-machine HA.
