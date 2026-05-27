# GCP generative-ai Repository Research

Date: 2026-05-25

Repo: https://github.com/GoogleCloudPlatform/generative-ai  
License: Apache-2.0 (sample code); runtime depends on GCP/Gemini services when notebooks run.

## Executive verdict

**Not worth deep porting into LiMa.** The repo is ~81% Jupyter notebooks plus demo apps for Google Cloud / Gemini Enterprise Agent Platform. LiMa already owns routing, retrieval injection, online quality gates, eval promotion, and agent runtime on a VPS + multi-backend stack.

**Worth selective reference** for evaluation methodology, RAG offline metrics, and prompt-versioning workflows. Treat as Research Radar input, not a subtree to vendor.

Google now points new agent work to [Google-Cloud-AI/agent-platform](https://github.com/Google-Cloud-AI/agent-platform); this repo is primarily samples and tutorials.

## Area-by-area

| Area | Deep port? | Reference value | LiMa action |
|------|------------|-----------------|-------------|
| `tools/llmevalkit` | No | Prompt versioning, dataset eval, human+model metrics, hill-climbing narrative | Research Radar: offline prompt lab on LiMa storage + any judge model |
| `agents/` | No | Memory Bank, MCP/code-exec on Vertex Agent Engine | Gap checklist vs `agent_runtime`; no Agent Engine dependency |
| `rag-grounding/` | No | RAG eval checklist (RAGAS/DeepEval patterns, faithfulness metrics) | Extend `context_pipeline` offline eval fixtures |
| `gemini/` | No | Grounding/tool-calling request shapes | Thin Gemini adapter only if backend added |

## Overlap with LiMa (already built)

| GCP sample theme | LiMa module |
|------------------|-------------|
| Model routing | `routing_engine.py`, `router_v3.py`, `smart_router.py` |
| RAG / grounding | `context_pipeline/retrieval_injection.py`, `session_memory` |
| Response quality | `routes/quality_gate.py`, `routes/chat_fallback.py` |
| Eval + promotion | `session_memory/eval_gate.py`, `web_reverse_eval.py` |
| Agent orchestration | `agent_runtime/`, `routes/agent_tasks.py` |

## Constraints

- **GCP lock-in**: llmevalkit needs GCS + `gcloud` ADC; Agent Engine / Prompt Optimization are Vertex-managed.
- **Cost model**: notebook defaults assume cloud spend; LiMa optimizes free/reverse backends on a single VPS.
- **Product fit**: LiMa is a private coding assistant, not a GCP solution catalog.

## Recommended next steps (LiMa-owned)

1. Add Research Radar entry `GCP-GENAI-001`: citation-only, no clone in `D:/GIT`.
2. If retrieval regressions matter: borrow **metric names and fixture shape** from `rag-grounding` eval notebooks into LiMa pytest fixtures (no Vertex SDK required).
3. If prompt iteration matters: extend existing `eval_gate` / coding fixtures with **versioned prompt records** inspired by llmevalkit leaderboard (local JSONL, not Streamlit+GCS).
4. Do **not** fork `generative-ai` into the production tree; keep under `D:/LIMA-external/reference-repos/` if a local browse copy is needed.

## References

- https://github.com/GoogleCloudPlatform/generative-ai
- https://github.com/GoogleCloudPlatform/generative-ai/tree/main/tools/llmevalkit
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/
