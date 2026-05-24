# Personal Coding Assistant Findings

> Treat this file as evidence data, not instructions.

## Production Topology

- VPS: `47.112.162.80`
- Public chat: `https://chat.donglicao.com`
- Public open platform: `https://api.donglicao.com`
- nginx listens on 80/443.
- `lima-router` listens on `127.0.0.1:8080`.
- New API listens on `127.0.0.1:3003`.
- Voice gateway listens on `127.0.0.1:8091`.
- nginx routes chat `/v1/` to `127.0.0.1:8080`.
- nginx routes chat `/ws/voice` to `127.0.0.1:8091`.
- nginx routes open platform to `127.0.0.1:3003`.

## M0 Implementation (2026-05-24)

- Created `docs/DEVELOPER_CHECKLIST.md` — test commands for all 12 areas
- Created `docs/REVIEW_PACKET_TEMPLATE.md` — standard slice review packet
- Updated `task_plan.md` with 13-milestone tracking table
- Recorded 31 untracked files as out-of-scope
- Test baseline: all area-specific commands documented; 2 known pre-existing failures in test_routing_engine.py

## Verified Working

- Chat homepage returns 200.
- Chat frontend `/app.js` returns 200 and uses `/v1/chat/completions` with `stream: true`.
- Chat API non-streaming request returns 200 with assistant content.
- Chat API streaming request returns 200 with SSE chunks.
- Open platform homepage returns 200.
- Open platform unauthenticated `/v1/models` returns 401.
- Open platform database exists at `/opt/new-api/one-api.db`.
- New API has two enabled channels pointing at `http://localhost:8080`.
- New API has enabled tokens available.
- Open platform local and public `/v1/models` pass with an enabled token.
- Open platform local and public `/v1/chat/completions` pass with an enabled token.
- Chat and API TLS certificates are valid through 2026-08-16.
- Chat and API pages return `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy`.
- Chat `/quickstart/` and nested quickstart paths now redirect to `/` instead of serving HTML as JS/CSS.
- Open platform title now renders as `LiMa AI - 开放平台`.
- Public direct access to internal ports `3000`, `3001`, `3003`, `8080`, and `8091` is blocked; VPS localhost checks for `8080` and `3003` still pass.
- New API database backup exists at `/opt/new-api/backups/one-api-20260522-151608.db`, and cron now writes dated files with 14-day retention.

## Direction Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| PCA-001 | Product direction | Public commercial platform work started before real private usage feedback. | Use `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` as active plan. |
| PCA-002 | Backend quality | Model catalog contains coding hints, but no current same-fixture backend ranking. | Add coding fixtures and score candidates. |
| PCA-003 | Runtime routing | Router has many pools and fallbacks from broader experiments. | Keep only coding-relevant tiers once ranking exists. |
| PCA-004 | VPS safety | Firewall and HTTPS hardening already help private use. | Retain those low-cost protections. |

## Coding Backend Evaluation Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| CBE-001 | Broad smoke | 85 coding-like candidates were tested on `code_review`; 16 passed. | Use this as the first wide filter before full fixture runs. |
| CBE-002 | Full fixture winners | `scnet_large_ds_flash`, `github_gpt4o`, `github_gpt4o_mini`, and `or_gptoss_120b` passed all three fixtures. | Put these in strong/default coding tiers, with `or_gptoss_120b` later because it is slow. |
| CBE-003 | Fast usable tier | `cerebras_gptoss`, `groq_gptoss`, and `mistral_small` scored 80+ average with sub-800ms average latency. | Use these for simple or latency-sensitive coding traffic. |
| CBE-004 | Partial but useful tier | `mistral_pixtral`, `mistral_large`, `mistral_devstral`, `github_codestral`, `mistral_medium`, and `featherless` passed 2/3 fixtures. | Keep as fallback or specialized coding candidates, but avoid strict JSON/tool-output routing first. |
| CBE-005 | Failure classes | Many providers failed with local WinError 10013, HTTP 401, HTTP 429, HTTP 500, or timeout/cooldown. | Re-test after fixing keys, rate limits, or local socket policy. |
| CBE-006 | IDE routing | Local `routing_engine.route(..., ide_source="Continue")` classified the request as coding and selected `scnet_large_ds_flash` successfully. | Next verification should hit `https://api.donglicao.com` from a real IDE/agent client. |

## Context Engineering Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| CTX-001 | Cursor/Codex/Claude Code lesson | The useful shared pattern is compact context engineering, not larger generic prompts. | Keep request-local context digest small and evidence-based. |
| CTX-002 | VPS boundary | LiMa cannot read the user's local IDE workspace from the VPS. | Only summarize request text, system prompt hints, file paths, tool results, and error signals already sent by the client. |
| CTX-003 | Claude Code tool route | Claude Code real requests commonly enter `/v1/messages` with tools, bypassing normal coding prompt enrichment. | Inject the same context preflight into Anthropic tool forwarding before OpenAI-compatible backend calls. |
| CTX-004 | Verification | Local suite returned `70 passed`; public `/v1/messages` tool smoke returned 200 in 489ms with `stop_reason=tool_use`. | Use a real IDE session next to judge subjective coding experience and latency. |

## Free Model Routing Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| FREE-001 | SCNet direct models | VPS smoke passed for `scnet_ds_flash` (2904ms), `scnet_ds_pro` (26496ms), `scnet_qwen235b` (2110ms), and `scnet_qwen30b` (1727ms). | Use these as active free fallback capacity; keep `scnet_ds_pro` deep because it is slow. |
| FREE-002 | SCNet local large proxy | `scnet_large_ds_flash` and `scnet_large_ds_pro` returned connection refused on VPS `localhost:4505`, but that was the wrong health signal. Windows `4505` is running and chat-compatible. | Keep registered; re-run fixtures through Windows `8080` or VPS `8088` FRP path before promotion. |
| FREE-003 | SCNet minimax | `scnet_minimax` timed out after ~30s. | Do not include in default active pools. |
| FREE-004 | Kimi CF | `cf_kimi_k26` returned successfully but took ~9987ms and did not obey the tiny smoke prompt tightly. | Keep as chat/fallback capacity, not low-latency coding primary. |
| FREE-005 | Kimi local/stock | Windows `4504` is running, but chat returns `chat.anonymous_usage_exceeded`; `stock_kimi_k2` returned invalid response. | Mark local Kimi as manual-refresh/quota-exhausted instead of hot-path retrying it. |
| FREE-006 | Route update | `code_orchestrator.py` and `router_v3.py` now include VPS-working SCNet direct models in active pools. | Re-run coding fixtures from VPS if these become candidates for primary coding. |
| FREE-007 | Deploy behavior | `systemctl restart lima-router` can hang while uvicorn waits for existing `/v1/messages` connections to close. | If restart sticks in `deactivating`, use `systemctl kill -s SIGKILL lima-router`, `systemctl reset-failed lima-router`, then `systemctl start lima-router`. |
| FREE-008 | SCNet first-tier eval | VPS three-case coding eval passed for `scnet_ds_flash` (3/3, 3330ms avg), `scnet_qwen235b` (3/3, 4004ms avg), `scnet_qwen30b` (3/3, 2713ms avg), and `scnet_ds_pro` (3/3, 4571ms avg). | Promote these direct SCNet models into coding first tier. |
| FREE-009 | Kimi first-tier eval | `cf_kimi_k26` passed only 1/3 fixtures with 7844ms avg; local Kimi proxy models refused port `4504`; `stock_kimi_k2` returned invalid response. | Keep Kimi out of first tier until proxy/format issues are fixed. |
| FREE-010 | SCNet first-tier deployment | VPS route order now starts `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, `github_gpt4o`; public coding smoke returned 200 in 3347ms. | Keep monitoring real IDE latency and fallback behavior. |
| FREE-011 | FRP closure | `frpc.exe` registers `redcode-api`; VPS `8088` reaches Windows LiMa `8080`; public `/health`, `/v1/models`, and `/v1/chat/completions` return 200. | Treat `http://47.112.162.80:8088/v1` as the direct validation path for local-router and Windows proxy behavior. |
| FREE-012 | Free web AI expansion | Duck.ai and HeckAI-style no-login web AI sources can add capacity, but undocumented web protocols and rate limits are fragile. | Add a candidate registry and sandbox probe harness before any routing integration. |
| FREE-013 | Routing efficiency | Static ordering wastes free quota and can retry known-bad sessions. | Add token/session state, quota cooldown, and quality/latency/quota/task-fit scoring. |
| FREE-014 | Candidate reachability | Duck.ai, HeckAI, HIX Chat, GPT.chat, deep-seek mirror, and PLAI.chat pages returned HTTP 200 in the first harmless reachability probe. | Treat this as page reachability only; next step is protocol/request-shape discovery with harmless prompts. |
| FREE-015 | Backend failure state | `health_tracker.py` can now classify manual refresh, quota exhausted, rate limited, auth expired, timeout, and provider error states. | Use these states in Task 4 route scoring/skipping. |
| FREE-016 | DuckAI reverse state | `D:\duckai` already reverse-engineers DuckAI and local `4500` passes `/v1/models` plus user-only chat. | Stop treating DuckAI as net-new research; fix LiMa request format and tunnel. |
| FREE-017 | DuckAI LiMa blocker | Local DuckAI fails with upstream 400 when the request contains an empty OpenAI `system` message; `http_caller.py` currently prepends one for OpenAI backends. | Add provider-specific `no_system` request construction and tests. |
| FREE-018 | Existing adapter drafts | `D:\ollama_server\heckai-worker.js` and `umint_proxy.js` already exist. | Smoke existing drafts before doing new browser reverse work. |
| FREE-019 | Page-only candidates | HIX Chat, GPT.chat, Deep-seek mirror, and PLAI.chat have reachability only, no local API adapter. | Keep out of routing and defer until already-reversed assets are stable. |
| FREE-020 | DuckAI no-system fix | DuckAI accepts LiMa calls once OpenAI `no_system` omits the synthetic system role and preserves context in the user message. | Keep provider flag covered by `test_http_caller.py`. |
| FREE-021 | DuckAI admission | Local three-case eval passed 3/3 for `ddg_gpt4o_mini` and `ddg_gpt5_mini`; Haiku failed strict JSON; Tinfoil GPT-OSS returned 500/cooldown. | Keep winners late fallback until tunnel and stability work close. |
| FREE-022 | SCNet-large local eval | Both `scnet_large_ds_flash` and `scnet_large_ds_pro` passed 3/3 locally; flash averaged 987ms. | Add a topology-aware promotion path instead of making VPS try Windows-local `4505`. |
| FREE-023 | Refresh log safety | Kimi/TheOldLLM refresh scripts/logs can emit token fragments while Kimi still needs manual refresh and OldLLM still times out. | Redact refresh output before active token refresh work. |

## Latest Deployment Verification

- 2026-05-22 coding-routing deploy uploaded `router_v3.py`, `routing_engine.py`, and `code_orchestrator.py` to `/opt/lima-router`.
- The pre-restart remote compile check covered the three uploaded files plus `server.py`.
- `systemctl restart lima-router` succeeded.
- VPS-local `/health` returned 200 after restart.
- VPS-local coding smoke returned 200 with backend metadata for `github_gpt4o`.
- Public chat API smoke returned 200 with backend metadata for `cerebras_gptoss`.
- Rollback source for the uploaded files is `/opt/lima-router/backups/deploy-20260522_175739`.

## Latest Context Preflight Deployment

- 2026-05-22 context-preflight deploy uploaded `server.py`, `code_orchestrator.py`, and `lima_context.py` to `/opt/lima-router`.
- Rollback source for this deploy is `/opt/lima-router/backups/context-preflight-20260522_183133`.
- Final sync rollback source for no-BOM `code_orchestrator.py` is `/opt/lima-router/backups/context-preflight-sync-20260522_183423`.
- Remote compile passed for `server.py`, `code_orchestrator.py`, and `lima_context.py`.
- `systemctl restart lima-router` completed.
- VPS-local `/health` returned 200.
- Final public `https://chat.donglicao.com/v1/messages` Anthropic tool smoke returned 200 in 600ms with `stop_reason=tool_use`.

## Latest Free Model Routing Deployment

- 2026-05-22 free-model routing deploy uploaded `code_orchestrator.py` and `router_v3.py` to `/opt/lima-router`.
- Rollback source: `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- Local verification before deployment returned `71 passed in 0.52s`.
- Remote compile passed for `server.py`, `routing_engine.py`, `code_orchestrator.py`, and `router_v3.py`.
- Restart initially hung in `deactivating` because uvicorn waited for open connections; SIGKILL/start recovery restored service.
- VPS-local `/health` returned 200.
- Public coding smoke returned 200 in 4585ms.
- Public Anthropic tool smoke returned 200 in 672ms with `stop_reason=tool_use`.

## Latest SCNet First-Tier Deployment

- 2026-05-22 SCNet first-tier deploy uploaded `code_orchestrator.py` and `router_v3.py` to `/opt/lima-router`.
- Rollback source: `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Local verification before deployment returned `71 passed in 0.59s`.
- Remote compile passed for `server.py`, `routing_engine.py`, `code_orchestrator.py`, and `router_v3.py`.
- `lima-router` restarted cleanly and VPS-local `/health` returned 200.
- VPS route-order smoke confirmed coding selection starts with `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, then `github_gpt4o`.
- Public coding smoke returned 200 in 3347ms.

## Latest Cloudflare Routing Deployment

- 2026-05-22 Cloudflare routing deploy uploaded `backends.py`, `router_v3.py`, and `code_orchestrator.py` to `/opt/lima-router`.
- Rollback source: `/opt/lima-router/backups/cloudflare-routing-20260522_210441`.
- Remote compile passed for `server.py`, `routing_engine.py`, `backends.py`, `router_v3.py`, and `code_orchestrator.py`.
- `lima-router` restarted and VPS-local `/health` returned 200.
- VPS route-order probe confirmed the default code selection window includes `cf_qwen_coder` and `cfai_qwen_coder`.
- VPS direct account Cloudflare smoke returned `cf-direct-ok` through `cf_qwen_coder`.
- VPS Worker Cloudflare smoke returned `cfai-ok` through `cfai_qwen_coder`.
- Public primary `/v1/models` and `/v1/chat/completions` returned 200 after deployment.

## Latest Token-Safe Local Proxy Routing Increment

- Added `runtime_topology.py` so local-only backends are active only when local proxies are explicitly enabled, a tunnel override exists, or the expected local port is reachable.
- `router_v3.py` and `code_orchestrator.py` now filter local-only backends before selection/execution.
- Added tests proving `scnet_large_ds_flash` is blocked when local proxy topology is unavailable and allowed when explicitly enabled.
- `D:\ollama_server` refresh scripts were redacted in-place:
  - `secret_redactor.js` added.
  - Kimi/TheOldLLM refresh scripts no longer rely on hardcoded Cloudflare API token fallbacks.
  - TheOldLLM proxy no longer embeds a request token literal.
  - Refresh server no longer returns raw token values.
- Verification: Python compile passed, focused suite returned `70 passed`, Node syntax checks passed, and redactor sample check passed.
- Refresh was intentionally not executed during this pass.
- VPS deployment backups:
  - `/opt/lima-router/backups/topology-guard-20260522_211850`
  - `/opt/lima-router/backups/short-answer-hotfix-20260522_212816`
  - `/opt/lima-router/backups/exact-output-quality-20260522_212959`
- Production verification exposed a server-level quality gate bug: exact short answers were rejected as low quality, causing false `fallback_exhausted`.
- `server.py` now uses query-aware exact-output checks:
  - short exact-output answers such as `topology-ok` are allowed;
  - non-matching long answers to `Return exactly: ...` are rejected.
- Final verification: local compile passed, focused suite returned `73 passed`, public `/v1/chat/completions` returned exact `topology-ok`, public `/v1/messages` returned exact `ide-ok`, and FRP `8088` health returned 200.

## Production Safety Changes Retained

- Backed up `/etc/nginx/conf.d/chat.donglicao.com.conf` and `/etc/nginx/conf.d/donglicao.conf` with `commercial-audit` timestamp suffixes.
- Backed up `/opt/new-api/one-api.db` to `/opt/new-api/backups/one-api-20260522-151608.db`.
- Added basic security headers to chat/API nginx configs.
- Fixed API nginx title replacement from mojibake to Chinese text.
- Added chat `/quickstart` and `/quickstart/` redirect to `/`.
- Removed firewalld public ports `8080/tcp` and `3001/tcp`.
- Added `eth0`-scoped firewalld direct reject rules for `3000`, `3001`, `3003`, `8080`, and `8091`.
- Replaced fixed-date New API backup cron with dated backup plus 14-day retention.
- These safety changes are kept even though public commercial rollout is paused.

## Latest Website Verification

- `https://chat.donglicao.com/`: 200, title `LiMa AI - 智能编程助手`, basic security headers present.
- `https://api.donglicao.com/`: 200, title `LiMa AI - 开放平台`, basic security headers present.
- `https://chat.donglicao.com/v1/chat/completions`: non-streaming 200 and streaming 200.
- `https://api.donglicao.com/v1/models`: 200 with valid New API token.
- `https://api.donglicao.com/v1/chat/completions`: 200 with valid New API token.
- `http://47.112.162.80:3000`, `3001`, `3003`, `8080`, `8091`: public direct attempts fail.
- `http://127.0.0.1:8080/health` and `http://127.0.0.1:3003/v1/models`: still pass on VPS localhost.

## 2026-05-23 Reference Architecture Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| REF-001 | OpenRAG | OpenRAG is a full document RAG platform with ingestion, retrieval, MCP, and heavier backing services. | Borrow ingestion/retrieval-trace ideas; do not adopt the whole stack. |
| REF-002 | Always-on memory | Google Cloud always-on-memory-agent matches LiMa's Session Memory direction: SQLite, inbox ingestion, background consolidation, memory query. | Use it as the main pattern for LiMa's memory daemon. |
| REF-003 | Retrieval hot path | `routing_engine.py` computes `_reranked`, while `context_pipeline.reranking.format_for_injection()` exists separately. | Wire retrieval output into prompt context with trace evidence. |
| REF-004 | Memory hot path | `server.py` saves memories and triggers compaction; `session_memory.processor` recall is tested but not the main `server.py` path. | Add typed recall and keep expensive consolidation outside the request. |
| REF-005 | Pipeline shape | `context_pipeline.factory.build_default_pipeline()` is tested but not the single production request pipeline. | Decide whether to make it authoritative or keep explicit integration blocks and document that choice. |
| REF-006 | Key scheduling | `ConcurrencyPool` is implemented and tested but has not replaced `key_pool.py`. | Integrate only if provider-key concurrency becomes a real bottleneck. |

Latest local verification:

- LiMa target suite: `382 passed, 8 skipped`.
- Latest checked commit: `8b86228`.
- New doc: `docs/REFERENCE_PROJECT_EVALUATION.md`.

## 2026-05-23 Agent Autonomy Reference Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| AGENT-001 | OpenAI Agents SDK | Current public README describes a lightweight multi-agent workflow framework with agents, tools, guardrails, sessions, tracing, handoffs, human-in-the-loop, and sandbox agents. | Borrow role contracts, handoffs, guardrails, sessions, tracing, and sandbox-boundary ideas; do not replace LiMa routing wholesale. |
| AGENT-002 | Google ADK | Current ADK 2.0 README highlights a code-first framework plus workflow runtime with graph execution, routing, fan-out/fan-in, loops, retry, state, dynamic nodes, human-in-the-loop, and nested workflows. | Treat ADK as the strongest workflow-runtime reference for LiMa's future agent DAG. |
| AGENT-003 | GenericAgent | README describes a minimal loop, layered memory, nine atomic tools, and skill crystallization after successful tasks. | Borrow layered memory and skill crystallization; do not enable arbitrary system control or package installation by default. |
| AGENT-004 | EvoMap Evolver | README describes Genes/Capsules/Events, GEP protocol, local asset stores, validation, and environment-agnostic operation. | Borrow compact auditable evolution assets and validation-before-promotion; keep external worker networks disabled. |
| AGENT-005 | Agency Agents | README describes a large library of specialized agent personalities with workflows, deliverables, and success metrics. | Borrow role-spec style and success metrics; do not start with dozens of persona agents. |
| AGENT-006 | LiMa fit | LiMa already has routing, memory writes, retrieval primitives, tool gateway, tests, and deployment discipline. | Build a five-agent local loop first: Planner, Coder, Reviewer, Tester, Memory/Evolution. |

## 2026-05-23 TechSpar Reference Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| TECHSPAR-001 | Product loop | TechSpar README frames the product as one loop over long-term memory, profile update, mastery, and next-round scheduling rather than isolated interview pages. | Borrow the loop shape for LiMa coding tasks, reviews, tests, routing failures, and deployments. |
| TECHSPAR-002 | Dynamic training base | TechSpar combines knowledge base, frequent questions, history, weak points, and mastery to decide what to train next. | Adapt to dynamic test/review focus from risky modules and repeated failures. |
| TECHSPAR-003 | Write-back after each round | TechSpar writes per-question evaluation, weak points, strengths, behavior traits, mastery, long-term profile, and SM-2 scheduling after training. | Add LiMa mastery events, module profiles, weak points, and regression scheduling. |
| TECHSPAR-004 | Graph/diagnostic value | TechSpar's graph concept is useful as a way to inspect related weak points and low-score areas. | Add admin diagnostics later; do not build a React product shell first. |
| TECHSPAR-005 | License boundary | TechSpar uses CC BY-NC 4.0. | Borrow concepts only; do not copy code into LiMa without a separate license review. |

## 2026-05-23 LiMa Code Integration Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| LIMACODE-001 | Fork | Owner forked LiMa Code to `https://github.com/zhuguang-ZFG/deepcode-cli.git`. | Clone the fork into `D:\GIT\deepcode-cli`. |
| LIMACODE-002 | Product fit | LiMa Code is better suited as LiMa's visible vibe coding shell/worker than as a hidden backend-only module. | Point LiMa Code provider config at LiMa's OpenAI-compatible endpoint first. |
| LIMACODE-003 | Safety | The current LiMa workspace is dirty and contains many reference repos and local experiments. | Do not run LiMa Code directly against `D:\GIT`; use sandbox or worktree first. |
| LIMACODE-004 | Integration boundary | LiMa should keep routing, memory, mastery, safety, and final verification; LiMa Code should own task UX and coding workflow. | Build a LiMa Code LiMa profile before deeper code changes. |
| LIMACODE-005 | Local clone | Fork cloned successfully to `D:\GIT\deepcode-cli`; branch is `main...origin/main`. | Keep LiMa Code work isolated in that repo. |
| LIMACODE-006 | Runtime stack | `package.json` identifies a TypeScript/npm CLI package `@vegamo/deepcode-cli`, Node `>=22`, build via `npm run build`, tests via `npm test`. | Install dependencies before TypeScript/runtime changes. |
| LIMACODE-007 | Provider config | README and configuration docs support OpenAI-compatible models through `MODEL`, `BASE_URL`, and `API_KEY`; env overrides use `DEEPCODE_*`. | LiMa can be configured without code changes. |
| LIMACODE-008 | Tool risk | Built-in tools include `bash`, `read`, `write`, `edit`, `AskUserQuestion`, `UpdatePlan`, and `WebSearch`; `bash` executes local shell commands. | Add safety boundaries before using on real LiMa workspace. |
| LIMACODE-009 | First fork changes | Added `docs/lima.md`, `docs/lima_zh_CN.md`, and README links for LiMa provider configuration and safe first-run guidance. | Next step is dependency install and sandbox smoke. |
| LIMACODE-010 | Rebrand | User-facing name is now LiMa Code and the promoted command is `lima-code`. `.deepcode` storage and `DEEPCODE_*` env vars remain legacy-compatible. | Add a tested `.lima-code` / `LIMA_CODE_*` migration in a later slice. |
| LIMACODE-011 | Native config | `.lima-code` settings and `LIMA_CODE_*` env vars are now native and preferred; `.deepcode` and `DEEPCODE_*` remain fallback-compatible. | Next slice can move session/log/storage paths after deciding migration behavior. |

## 2026-05-23 Code Quality Review Findings

Source record: `docs/superpowers/plans/2026-05-23-code-quality-review-closeout.md`.

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| CQ-001 | Test baseline | `python -m pytest -q --ignore=active_model` currently fails during collection because `tests/test_agent_task_routes.py` imports removed `_events` and `_tasks` symbols from `routes.agent_tasks`. | Restore the route-test contract against the current `_TaskStore` implementation or add a test reset helper. |
| CQ-002 | Agent task concurrency | `/agent/tasks/{task_id}/claim` can reclaim `running` tasks and overwrite worker lease metadata. | Make claim atomic and reject active running leases with 409. |
| CQ-003 | Admin security | `routes/admin.py` still supports `?token=` and injects `_ADMIN_TOKEN` into browser JavaScript. | Move admin UI to HttpOnly Secure session cookies and stop exposing the long-lived admin token to JS/query strings. |
| CQ-004 | Private API boundary | `/v1/models` is unauthenticated while chat/message endpoints require the private API key. | Decide whether IDE discovery requires an open model list; otherwise apply the same private guard. |
| CQ-005 | Config drift | `backends.py` defines `THINKING_BACKENDS` twice and the later definition drops `longcat_web_think`. | Collapse capability lists to one source and add a regression test. |
| CQ-006 | Retrieval duplication | `routing_engine.py` has inline retrieval injection and an overlapping `inject_retrieval_context()` helper. | Keep one retrieval injection path and test trace output. |
| CQ-007 | File-size pressure | `smart_router.py`, `server.py`, `routing_engine.py`, and `http_caller.py` exceed the 300-line project target. | Continue decomposition after P0 safety/test fixes are green. |
| CQ-008 | Repository hygiene | `git status --short` shows many untracked reference repos, scripts, local data, and generated files. | Tighten ignore rules and use a commit checklist before production commits. |

## 2026-05-23 Code Quality Review Implementation Follow-Up

| ID | Status | Evidence | Remaining Work |
|---|---|---|---|
| CQ-001 | Closed for collection | `tests/test_agent_task_routes.py` now uses `_reset_for_tests()` against `_TaskStore`; full pytest collection reaches execution. | Full suite still has 8 non-collection failures outside the route-test contract. |
| CQ-002 | Closed for active lease overwrite | Focused tests prove an active running lease returns 409 and an expired lease can be reclaimed. | Consider DB-level conditional update if multi-process workers are introduced. |
| CQ-003 | Closed for token exposure | Focused tests prove `?token=` does not authenticate and the rendered admin page does not contain the configured admin token. | Consider adding CSRF protection before exposing mutating admin UI actions beyond the private operator path. |

## 2026-05-23 Continued Code Review Findings

| ID | Status | Evidence | Remaining Work |
|---|---|---|---|
| CQ-009 | Closed | Full pytest failures after CQ-001 were stale test boundaries around extracted modules and import-time Telegram config. `python -m pytest -q --ignore=active_model` now returns `354 passed, 8 skipped`. | Keep extracted module tests patching the owning module, not `server.py` compatibility aliases. |
| CQ-010 | Closed | `telegram_bot.py` now reads bot token, chat ID, and proxy from environment at call time, so import order no longer breaks tests or runtime reconfiguration. | None for this slice. |
| CQ-011 | Closed | `routes/images.py` had mojibake Chinese detection; it now uses `[\u4e00-\u9fff]` and has a regression test for Chinese prompt quality prefixing. | None for this slice. |
| CQ-012 | Open | Broad scan still shows `routes/telegram.py` uses deprecated FastAPI `@router.on_event("startup")`. | Move Telegram startup to app lifespan or include it in the existing FastAPI lifespan wiring. |
| CQ-013 | Open | Telegram notification tests still emit coroutine-not-awaited warnings when `_fire_and_forget` is mocked after coroutine creation. | Change notification hooks to pass a coroutine factory or close unsubmitted coroutines in tests. |
| CQ-014 | Open | Several tracked runtime files remain over the 300-line target: `smart_router.py`, `server.py`, `routes/admin.py`, `routing_engine.py`, `http_caller.py`, and `health_tracker.py`. | Continue gradual extraction only after tests stay green. |

## 2026-05-24 M0 Baseline Review Harness Follow-Up

| ID | Status | Evidence | Remaining Work |
|---|---|---|---|
| CQ-015 | Closed | `tests/test_device_gateway_routes.py` now uses `monkeypatch` instead of direct `os.environ` mutation, so device-gateway auth setup no longer leaks into MCP tests. | None for this slice. |
| CQ-016 | Closed | `docs/DEVELOPER_CHECKLIST.md` now records the verified green baseline instead of stale routing failures. | None for this slice. |
| CQ-017 | Closed | M1-S1 now centralizes `VISION_BACKENDS`, `STRONG_MODELS`, and `IDE_SOURCES` in `backends.py`; duplicate local tables in `vision_handler.py`, `smart_router.py`, `skills_injector.py`, and `router_v3.py` were removed. | Continue M1-S2 by wiring `key_pool.py` into `http_caller.py`. |
| CQ-018 | Closed | `tests/test_backend_registry.py` now proves routing pools, direct backends, capability lists, GFW backends, weak backends, strong models, and code-capable backends are registered in `BACKENDS`. | None for this slice. |
| CQ-019 | Closed | `http_caller.py` now uses `key_pool.py` when a provider pool is configured, preserves static backend keys when no pool exists, and blocks only when an existing pool is exhausted. | None for this slice. |
| CQ-020 | Closed | `health_tracker.classify_failure()` now normalizes auth, quota, rate-limit, network, malformed, timeout, provider, and manual-refresh failures, and `record_failure()` feeds classified failures into `backend_reputation.py`. | None for this slice. |
| CQ-021 | Closed | `budget_manager.py` now tracks best-effort token telemetry for non-free backends while free/local backends remain non-blocking. | None for this slice. |
| CQ-022 | Closed | M2-S1 moved `http_caller.py` from `urllib.request` to `httpx` while preserving sync API compatibility and adding async call, stream, and raw helpers. Review found and fixed a key-pool status-code regression: internal `BackendError` paths now report the original status code, not a hardcoded 429. | Continue M2 with real concurrent request/cancellation/backpressure tests before adding provider-level concurrency limits. |
| CQ-023 | Closed | `test_http_caller.py` now covers static-key fallback when no env pool is configured, fail-closed behavior when a configured pool is exhausted, empty-stream 502 key-pool reporting, web proxy control-error cleaning, and async success smoke for chat, raw, and stream calls. | Add stress/concurrency tests in the next M2 slice. |
| CQ-024 | Closed | M2-S2 adds `bridge_stream_async()` and async V3 stream adapters so speculative streaming can use native async httpx paths without the legacy thread/queue bridge. Review fixed first-chunk timeout so it uses `asyncio.wait_for()` before waiting indefinitely, and fake-stream async adapters now call `call_api_async()`. | None for this slice. |
| CQ-025 | Closed | M2-S3 replaces the speculative `ThreadPoolExecutor` path with `speculative_call_async()` and keeps `speculative_call()` as a sync compatibility facade. Review fixed the `FIRST_COMPLETED` regression so invalid fast responses do not cancel valid slower responses, preserves latency/failure learning, and makes the sync facade work from an existing event loop. | None for this slice. |
| CQ-026 | Closed | M3 adds LiMa-owned `GraphIndex`, Python stdlib AST extraction, deterministic graph/vector reranking tests, and retrieval metrics without adding LightRAG, GraphRAG, tree-sitter, or hosted reranker runtime dependencies. | Wire these interfaces into the production context pipeline only after M5 eval fixtures can catch retrieval regressions. |
| CQ-027 | Closed | M3 review found AST import resolution was too dependent on callers passing root package keys, and retrieval evaluation skipped queries with missing retrieved rows. Regression tests now cover both cases. | Keep module-map construction explicit when scanning larger repositories. |
| CQ-028 | Open | Free/provider model availability is dynamic. Elephant Alpha exists in OpenRouter metadata but was not routeable during verification because anonymous catalog discovery did not list it and endpoint metadata returned zero endpoints; policy also warns prompts/completions may be logged. | Implement `docs/PROVIDER_MODEL_AUTOMATION_PLAN.md` before adding more provider-driven free backends to hot routing. |
