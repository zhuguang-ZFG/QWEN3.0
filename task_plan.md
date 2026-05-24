# Personal Coding Assistant Task Plan

> Created: 2026-05-22
> Scope: private coding assistant use of LiMa, chat.donglicao.com, and api.donglicao.com.
> Rule: prioritize evidence from coding tasks over public-platform complexity.
>
> ## Implementation Plan (2026-05-24)
>
> Source: `docs/superpowers/plans/2026-05-24-lima-implementation-review-plan.md`
> Mode: user implements, Codex reviews. 1 slice = 1 commit.
>
> | M# | Name | Status | Started |
> |----|------|--------|---------|
> | M0 | Baseline & Review Harness | complete | 2026-05-24 |
> | M1 | Router, Backend Registry, Key Pool | complete | 2026-05-24 |
> | M2 | Async & Concurrency | complete | 2026-05-24 |
> | M3 | Context Graph, AST, Reranking | complete | 2026-05-24 |
> | M4 | Memory Taxonomy & Redaction | complete | 2026-05-24 |
> | M5 | Eval, Quality Gate, Structured Output | pending | - |
> | M6 | Observability & Metrics | pending | - |
> | M7 | Worker Governance, Tool Gateway, MCP, A2A | pending | - |
> | M8 | Sandbox Evaluation | pending | - |
> | M9 | Streaming & Progress Events | pending | - |
> | M10 | Data Workbench | pending | - |
> | M11 | DevOps, Deployment, Terminal UX | pending | - |
> | M12 | Hardware Companion | pending | - |
>
> ### Error Log
>
> | # | Milestone | Error | Attempt | Resolution |
> |---|-----------|-------|---------|------------|
> | 1 | M0 | Device gateway route tests leaked `LIMA_API_KEY` through `os.environ`, causing MCP auth tests to fail in the full suite. | Reproduced with `python -m pytest tests/test_device_gateway_routes.py tests/test_mcp_tools.py -q --ignore=active_model`. | Replaced direct environment mutation with a `monkeypatch` autouse fixture and updated the baseline. |
> | 2 | M2-S1 | Review found internal `BackendError` paths in `http_caller.py` were reporting key-pool failures as 429 instead of preserving the real status code. | Added an empty-stream regression that fails if a 502 is reported as 429, plus restored key-pool fallback coverage. | `BackendError` handlers now pass `e.status_code`; focused tests cover sync, async, stream, static fallback, and exhausted-pool behavior. |
> | 3 | M2-S3 | Async speculative execution returned failure when the fastest completed task produced an invalid short answer, because pending slower tasks were cancelled immediately. | Added a regression where `fast_bad` returns first and `slow_good` returns a valid response later. | `speculative_call_async()` now loops through completed tasks until a valid winner or timeout, then cancels and awaits pending tasks. |
> | 4 | M3-S2 | `StdlibAstExtractor.extract_relations()` required the caller to include a root package key such as `sample_repo`, so `from sample_repo.module_b import helper` missed relations when only `module_b` was mapped. | Added a leaf-module import regression. | Import resolution now checks full module name, root package, and leaf module before dropping the relation. |
> | 5 | M3-S4 | `evaluate_queries()` used zip-style pairing and silently ignored expected queries when the retrieved-results list was shorter. | Added a missing-retrieval regression. | Evaluation now enumerates every query and treats missing retrieved rows as empty misses. |
> | 6 | M4-S3 | `save_memory()` used `sanitize_for_memory(text) or text`, so critical sanitizer rejections such as SSH private keys could fall back to raw secret storage. Promotion evidence also entered memory detail and audit logs without shared redaction. | Added regressions for private-key save and promotion evidence redaction. | Storage now uses `_sanitize_storage_text()` and never falls back to raw text after a sanitizer rejection; promotion evidence is sanitized before detail/audit writes. |

## Goal

Turn the existing LiMa router into a private coding assistant that ranks coding backends, routes IDE/agent traffic to the best tier, and remains simple enough to operate on the VPS.

## Phases

| Phase | Status | Exit Criteria |
|---|---|---|
| 1. Website/VPS baseline audit | Complete | HTTPS, public endpoints, firewall exposure, and API smoke checks are known. |
| 2. Direction reset | Complete | Commercial code/docs are removed and personal coding assistant plan is active. |
| 3. Coding backend evaluation | Complete | Repeatable coding fixtures and backend score output exist. |
| 4. Personal routing tiers | Complete | Fast, primary, strong, and fallback coding tiers are configured from evidence. |
| 5. IDE/agent verification | Complete | Claude Code CLI, OpenAI-compatible IDE smoke, and Anthropic-compatible IDE smoke use the private endpoint successfully. |
| 6. Context preflight | Complete | Coding and Anthropic tool routes receive a compact request-local context digest. |
| 7. Free model routing refresh | Complete | VPS-working SCNet/Kimi-family free models are documented and active where safe. |
| 8. SCNet/Kimi first-tier eval | Complete | Direct SCNet models promoted; Kimi remains fallback/inactive until fixed. |
| 9. Local proxy + FRP closure | Complete | VPS `8088` reaches Windows LiMa `8080`; public health/models/chat smokes pass. |
| 10. Free web AI expansion | Complete | Candidate registry, harmless probes, and admission decisions exist; unsafe page-only candidates remain sandboxed. |
| 11. Stability + free routing optimization | Complete | Failure-state classification, terminal-state filtering, unproven web-adapter exclusion, and quota-aware scoring are implemented and deployed. |
| 12. Local reverse AI inventory | Complete | Already-reversed adapters are separated from page-only candidates and documented. |
| 13. Local reverse AI integration fixes | Complete | DuckAI no-system path is implemented, DuckAI/SCNet-large evals are recorded, Kimi and OldLLM are gated by current failures. |
| 14. Cloudflare routing deployment | Complete | Direct and Worker Cloudflare coding capacity are routed, deployed, and smoke-tested on VPS. |
| 15. Token-safe refresh and topology-aware proxy promotion | Complete | Redaction, topology guard, VPS deployment, exact-output quality hotfix, and public IDE/API smokes pass. |

## Current Evidence

- `https://chat.donglicao.com/` returns 200.
- `https://api.donglicao.com/` returns 200.
- Chat `/v1/chat/completions` works for non-streaming and streaming when the request body is valid JSON.
- Open platform New API local and public `/v1/models` and `/v1/chat/completions` work with an enabled platform token.
- TLS certificates are valid until 2026-08-16 for both chat and API domains.
- Basic security headers now return on chat and API pages.
- Open platform title now renders as `LiMa AI - 开放平台`.
- Direct public access to internal ports `3000`, `3001`, `3003`, `8080`, and `8091` is blocked on `eth0`; localhost access still works.
- New API database backup cron may remain as cheap protection for existing VPS state.
- `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` defines the active direction.
- `scripts/eval_coding_backends.py` ranks coding candidates with three deterministic fixtures.
- Broad smoke covered 85 coding-like candidates and found 16 passers on `code_review`.
- Full fixture run covered those 16 passers.
- Full fixture 3/3 passers: `scnet_large_ds_flash`, `github_gpt4o`, `github_gpt4o_mini`, `or_gptoss_120b`.
- Fast usable tier: `cerebras_gptoss`, `groq_gptoss`, and `mistral_small` scored 80+ average under 800ms average latency.
- Local routing smoke with `ide_source=Continue` selected `scnet_large_ds_flash` for a coding request and returned successfully.
- VPS deployment uploaded the evidence-backed coding route files and restarted `lima-router`.
- VPS-local coding smoke returned 200 and routed to `github_gpt4o`.
- Public chat API smoke returned 200 and routed to `cerebras_gptoss`.
- `lima_context.py` now builds a request-local context digest from IDE/source hints, workspace hints, task shape, language, file paths, and tool/error signals.
- Normal coding routes inject the digest through `code_orchestrator.enhance_context`.
- Claude Code Anthropic tool routes inject the digest through `server._inject_anthropic_context_preflight`.
- Local verification for the context-preflight change returned `70 passed in 0.51s`.
- VPS context-preflight deployment backup: `/opt/lima-router/backups/context-preflight-20260522_183133`.
- Final no-BOM sync backup: `/opt/lima-router/backups/context-preflight-sync-20260522_183423`.
- VPS-local `/health` returned 200 after the context-preflight restart.
- Final public Anthropic `/v1/messages` tool smoke returned 200 in 600ms with `stop_reason=tool_use`.
- VPS free-model smoke passed for `scnet_ds_flash`, `scnet_ds_pro`, `scnet_qwen235b`, `scnet_qwen30b`, and `cf_kimi_k26`.
- `scnet_large_*` and local `kimi*` proxy models are Windows-local services. The earlier VPS `localhost:4505/4504` checks were the wrong health signal for the FRP architecture.
- `docs/FREE_MODEL_ROUTING_STATUS.md` records the free-model status table.
- `docs/LIMA_MEMORY.md` records the detailed durable memory for future sessions.
- Free-model routing deployment backup: `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- Post-deploy public coding smoke returned 200 in 4585ms.
- Post-deploy public Anthropic tool smoke returned 200 in 672ms with `stop_reason=tool_use`.
- VPS first-tier eval found direct SCNet winners: `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, and `scnet_ds_pro`.
- Kimi did not qualify for first tier in the same eval; CF Kimi passed 1/3 and local Kimi proxy models were unreachable.
- `code_orchestrator.py` and `router_v3.py` now put direct SCNet winners at the front of coding pools.
- SCNet first-tier deployment backup: `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Post-deploy route-order smoke confirmed coding starts with `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, then `github_gpt4o`.
- Post-deploy public coding smoke returned 200 in 3347ms.
- Windows local proxy closure:
  - `D:\GIT\local_router_start.bat` now starts `server.py` on port `8080` and starts FRP.
  - Windows `4505` SCNet-large proxy is running and chat-compatible.
  - Windows `4504` Kimi proxy is running, but chat returns `chat.anonymous_usage_exceeded`.
  - `frpc.exe` registers `redcode-api`.
  - After opening VPS `8088/tcp`, `http://47.112.162.80:8088/health`, `/v1/models`, and `/v1/chat/completions` returned HTTP 200.
- Completed no-login web AI expansion, stability, and free routing optimization docs and implementation.
- Added sandbox candidate registry and probe harness for no-login web AI candidates.
- Added backend failure-state classification for auth/quota/rate-limit/session/timeout cases.
- Local reverse AI inventory now records that DuckAI, SCNet-large, Kimi, TheOldLLM, g4f, HeckAI draft, and page-only candidates are different states and should not be handled as one bucket.
- `docs/superpowers/plans/2026-05-22-local-reverse-ai-integration.md` is a completed execution record.
- DuckAI `no_system` integration is implemented; six DuckAI models are registered and only admitted as late fallback.
- DuckAI route admission passed for `ddg_gpt4o_mini` and `ddg_gpt5_mini`; SCNet-large local eval passed for both local proxy models.
- Cloudflare routing deployment backup: `/opt/lima-router/backups/cloudflare-routing-20260522_210441`.
- VPS code route selection now includes `cf_qwen_coder` and `cfai_qwen_coder` inside the default fallback window.
- VPS direct Cloudflare smoke returned `cf-direct-ok`; VPS Worker Cloudflare smoke returned `cfai-ok`.
- Public primary `/v1/models` and `/v1/chat/completions` returned 200 after the Cloudflare deployment.
- Token-safe local proxy routing increment:
  - `runtime_topology.py` added.
  - `router_v3.py` and `code_orchestrator.py` now filter local-only proxy backends.
  - `D:\ollama_server` refresh scripts were redacted in-place and no longer return raw token values.
  - VPS deployment backups:
    - `/opt/lima-router/backups/topology-guard-20260522_211850`
    - `/opt/lima-router/backups/short-answer-hotfix-20260522_212816`
    - `/opt/lima-router/backups/exact-output-quality-20260522_212959`
  - `server.py` exact-output quality gate hotfix prevents false `fallback_exhausted` on short direct-answer prompts.
  - Final local verification returned `73 passed`.
  - Public `/v1/chat/completions` returned exact `topology-ok`; public `/v1/messages` returned exact `ide-ok`; FRP `8088` health returned 200.
- Open phase completion:
  - `docs/IDE_AGENT_VERIFICATION.md` records OpenAI-compatible, Anthropic-compatible, and real Claude Code CLI verification.
  - `docs/FREE_WEB_AI_ADMISSION.md` and `data/free_web_ai_admission.json` record no-login web AI admission decisions.
  - `route_scorer.py` adds deterministic quality/stability/latency/quota/task-fit scoring.
  - `routing_engine.py` skips cooled-down terminal auth/quota/manual-refresh states and excludes unproven web adapters from IDE routes.
  - Local verification returned `86 passed`.
  - VPS backup: `/opt/lima-router/backups/complete-open-phases-20260522_214621`.
  - Public `/v1/chat/completions` returned exact `phase-complete-ok`; public `/v1/messages` returned exact `ide-agent-complete`; Claude Code CLI returned exact `claude-cli-ok`.

## Next Risks To Close

- Code quality review closeout on 2026-05-23 added `docs/superpowers/plans/2026-05-23-code-quality-review-closeout.md`. P0 implementation status:
  1. Route-test collection restored for the current SQLite-backed task store.
  2. `/agent/tasks/{task_id}/claim` now rejects active running leases and allows expired lease reclaim.
  3. Admin HTML no longer supports query-token login or raw-token JavaScript injection; login uses a signed HttpOnly Secure session cookie.
- Full local pytest collection now reaches execution but still reports 8 failures outside this slice: request stats, stream footer, and Telegram bot tests.
- Continued code review pass closed those 8 failures. Current local suite: `354 passed, 8 skipped`.
- Remaining non-failing cleanup: migrate `routes/telegram.py` startup from deprecated `on_event`, remove Telegram notify coroutine warnings, and continue hot-path file decomposition.
- More backends should be re-evaluated as keys, rate limits, and local socket policy failures are fixed.
- A private access policy for IDE/agent use needs to stay simple and explicit.
- `/v1/models` remains an explicit private-boundary decision: keep open only if IDE discovery requires it; otherwise apply `require_private_api_key`.
- Backend capability lists and retrieval injection paths need consolidation after P0 fixes are green.
- If Kimi local or SCNet-large proxy models are needed, verify them through the Windows LiMa `8080` path or the VPS `8088` FRP path, not VPS `localhost:4504/4505`.
- Page-only no-login web AI candidates remain sandbox-only until a real adapter and model-level smoke exist.
- Token refresh scripts are now safer to run, but refresh itself still needs a controlled pass with environment variables set and manual login/session state verified.

## 2026-05-23 Reference Project Reassessment

User requested a full codebase status calibration, documentation update, and renewed review of OpenRAG plus Google Cloud always-on-memory-agent.

Current outcome:

- Latest checked commit: `8b86228`.
- LiMa target-suite verification: `382 passed, 8 skipped`.
- New source-of-truth evaluation doc: `docs/REFERENCE_PROJECT_EVALUATION.md`.

Decision:

- OpenRAG is a useful reference for knowledge ingestion, retrieval traces, MCP knowledge tools, and document parsing.
- OpenRAG should not be copied wholesale; OpenSearch/Langflow/Next.js are too heavy for the current personal VPS backend.
- always-on-memory-agent is the stronger near-term reference because LiMa already has Session Memory and needs background consolidation.

Next work items:

1. Continue server.py decomposition: extract chat/completions and Anthropic handlers into routes/ modules.
2. Consolidate BACKENDS to single source (eliminate smart_router.BACKENDS duplication).
3. Wire key_pool.py into http_caller.py for multi-key providers.
4. Add `LiMa Task Prompt Contract v0.1` using the KERNEL pattern as a task-authoring rule:
   - Keep task goal simple and single-purpose.
   - Make success criteria easy to verify.
   - Avoid time-sensitive wording unless a concrete date/source is provided.
   - Keep each task narrow enough for one worker loop.
   - Include explicit constraints and non-goals.
   - Use a fixed structure: `Context`, `Task`, `Constraints`, `Verify`, `Output`.
   - Apply this first to `/agent/tasks`, LiMa Code worker prompts, role prompts, and candidate skill extraction.
5. Add `LiMa Code Hooks + Skill Auto-Activation v0.1` after autonomous worker v0.2 lifecycle controls are implemented:
   - Add a `skill-rules.json`-style rules file for prompt/path/content-based skill activation.
   - Add post-task, post-edit, and stop checkpoints that record touched files, tests run, failures, and review requirements.
   - Add `.lima-code/dev/active/<task>/plan.md`, `context.md`, and `tasks.md` for long-running worker context.
   - Add `/lima docs` and `/lima docs-update` slash commands for worker-local dev docs.
   - Require final worker summaries to state changed files, tests run, remaining risks, and review status.
   - Keep this behind repo allowlist, runtime budget, stop marker, audit, and failure quarantine controls.
6. Add `LiMa Policy Guidelines Engine v0.1` inspired by Parlant after hooks and skill activation exist:
   - Define condition-action guidelines for task policy, role activation, tool permission, and review gates.
   - Support guideline dependencies and exclusions so incompatible modes cannot activate together.
   - Map journeys to LiMa task lifecycle states such as `accepted`, `claimed`, `running`, `needs_review`, `approved`, `rejected`, and `applied`.
   - Activate tools only when observations match the task policy, not by default.
   - Record explainability traces: why a guideline, skill, role, or tool was activated.
   - Borrow Parlant's control ideas only; do not import the full customer-facing agent framework unless a later design proves it is worth the weight.

## Errors Encountered

| Time | Error | Resolution |
|---|---|---|
| 2026-05-22 | SSH nested shell quoting failed while querying New API database. | Replaced nested quoting with a base64-encoded remote Python script. |
| 2026-05-22 | PowerShell `curl` JSON body caused server JSONDecodeError. | Retested with Python JSON serialization; chat non-stream and stream passed. |
| 2026-05-22 | Local GBK console failed when printing Chinese audit output. | Re-ran scripts with `PYTHONIOENCODING=utf-8`. |
| 2026-05-22 | firewalld rich rules did not block podman/host port `3000`. | Added `eth0`-scoped firewalld direct reject rules; localhost proxy path remains open. |
| 2026-05-22 | Commercial direction became premature before real personal use. | Switched active plan to private coding assistant and removed billing/public-platform artifacts. |
| 2026-05-22 | Initial context-preflight integration test failed because `enhance_context` did not inject the digest yet. | Added digest injection and verified `tests/test_lima_context.py` passed. |
| 2026-05-22 | Some registered free models were not actually production-live. | Ran VPS smoke and moved only working SCNet direct models into active fallback pools. |
| 2026-05-22 | `systemctl restart lima-router` hung while uvicorn waited for open connections. | Killed the stuck service process, reset failed state, started service, and verified `/health` plus public smokes. |
| 2026-05-22 | Public `/v1/chat/completions` returned `router_fallback_exhausted` for `Return exactly: topology-ok` even though direct backends worked. | Made `server.py` quality checks query-aware for exact-output prompts; verified exact OpenAI and Anthropic public smokes. |
