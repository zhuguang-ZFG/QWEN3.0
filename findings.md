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
