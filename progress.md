# Personal Coding Assistant Progress

> Created: 2026-05-22

## 2026-05-22 Website Baseline

- Started persistent plan for closing chat/open-platform website issues.
- Reused prior evidence instead of repeating known-good checks blindly.
- Confirmed previous open-platform token test succeeded:
  - New API DB found at `/opt/new-api/one-api.db`.
  - Enabled channels point to `http://localhost:8080`.
  - Enabled tokens exist.
  - Local and public model/chat requests returned 200.
- Ran broader production audit for static assets, TLS/security headers, logs, backup, firewall exposure, and UI encoding.

## 2026-05-22 Production Audit And Closure

- Verified TLS expiry:
  - `chat.donglicao.com`: 2026-08-16 13:21:14 GMT.
  - `api.donglicao.com`: 2026-08-16 09:20:03 GMT.
- Found open platform title mojibake and fixed nginx sub_filter replacement.
- Found missing basic security headers and added them to chat/API nginx configs.
- Found chat `/quickstart/` serving fallback HTML for nested static paths and redirected it to `/`.
- Found direct public exposure risk for internal ports. Removed firewalld public ports `8080/3001` and added `eth0` direct reject rules for `3000/3001/3003/8080/8091`.
- Found New API backup cron overwriting a fixed dated file. Replaced it with dated daily backup and 14-day retention.
- Verified no regression:
  - Chat page/API non-stream/API stream all returned 200.
  - Open platform page/models/chat all returned 200 with valid token.
  - Internal localhost services still work for nginx.
  - Public direct internal ports are no longer reachable.

## 2026-05-22 Direction Reset

- User confirmed the product is a private personal coding assistant, not a commercial open platform.
- Added `docs/PERSONAL_CODING_ASSISTANT_PLAN.md`.
- Removed billing/quota/usage commercial modules and commercial tests from the active worktree.
- Removed active payment, public registration, open-platform upgrade, commercial roadmap, and commercial readiness docs.
- Removed commercial wiring from `server.py`, `routes/admin.py`, and deploy preflight references.

## Next Personal Assistant Work

- Validate one real IDE or terminal-agent coding workflow against the private endpoint.
- Re-test failed providers when more backend keys/rate limits/local socket policy are healthy.

## 2026-05-22 Coding Backend Eval And Routing

- Added `coding_eval.py`, `scripts/eval_coding_backends.py`, and three coding fixtures under `evals/coding_cases/`.
- Added unit tests for case loading, candidate detection, grading, run failure handling, and Markdown report ranking.
- User challenged the first ranking as too narrow; expanded from the 10-backend shortlist to a full 85-candidate smoke.
- Broad smoke found 16 `code_review` passers.
- Ran full 3-case eval for those 16 passers:
  - 3/3 pass: `scnet_large_ds_flash`, `github_gpt4o`, `github_gpt4o_mini`, `or_gptoss_120b`.
  - Fast 80+ score under 800ms: `cerebras_gptoss`, `groq_gptoss`, `mistral_small`.
  - Useful 2/3 fallback tier: `mistral_pixtral`, `mistral_large`, `mistral_devstral`, `github_codestral`, `mistral_medium`, `featherless`.
- Updated `code_orchestrator.POOLS` and `router_v3.POOLS["code"]` so the wider evidence-backed coding pool is tried first.
- Added Continue/VS Code detection to `routing_engine` and `router_v3`.
- Local IDE-routing smoke passed: `ide_source=Continue` produced `request_type=code_standard`, `scenario=coding`, backend `scnet_large_ds_flash`, and a real response in 1406ms.

## 2026-05-22 VPS Deployment

- Deployed the coding-routing changes to `/opt/lima-router` on VPS `47.112.162.80`.
- Uploaded runtime files only: `router_v3.py`, `routing_engine.py`, and `code_orchestrator.py`.
- Remote backup directory: `/opt/lima-router/backups/deploy-20260522_175739`.
- Remote `py_compile` passed for `router_v3.py`, `routing_engine.py`, `code_orchestrator.py`, and `server.py`.
- Restarted `lima-router` through `systemctl`.
- VPS local `/health` returned 200.
- VPS local OpenAI-compatible coding smoke returned 200 and routed to `github_gpt4o`.
- Public `https://chat.donglicao.com/v1/chat/completions` smoke returned 200 and routed to `cerebras_gptoss`.

## 2026-05-22 Claude Code Speed Fix

- Found the Claude Code slow path: requests with `tools` use the Anthropic `/v1/messages` tool branch, not the normal coding pool.
- Reordered `TOOL_TIER1_BACKENDS` to front-load fast tool-compatible backends: `groq_gptoss_20b`, `cerebras_gptoss`, `groq_gptoss`, GitHub, and Mistral.
- Changed tool backend retry behavior so one request tries distinct backends instead of retrying the same failed backend repeatedly.
- Added a regression test for distinct fast tool backend iteration.
- Deployed `server.py` to VPS with backup at `/opt/lima-router/backups/speed-20260522_181808`.
- Remote compile and `/health` passed after restart.
- VPS local Anthropic tool smoke returned 200 in 393ms with a real `tool_use` from `groq_gptoss_20b`.
- Public `https://chat.donglicao.com/v1/messages` tool smoke returned 200 in 819ms with a real `tool_use`.

## 2026-05-22 IDE Context Preflight

- Created `docs/superpowers/plans/2026-05-22-ide-context-preflight.md` and executed it task-by-task.
- Added `lima_context.py` with request-local context digest extraction for IDE source, workspace hints, task shape, language, file paths, and tool/error signals.
- Added `tests/test_lima_context.py` covering digest extraction, trivial-chat no-op behavior, max length, tool result summarization, and `code_orchestrator.enhance_context` integration.
- Injected the digest into normal coding route prompts through `code_orchestrator.enhance_context`.
- Injected the digest into Claude Code Anthropic `/v1/messages` tool requests through `server._inject_anthropic_context_preflight`.
- Kept the fast tool backend order and distinct-backend retry behavior intact.
- Local verification passed:
  - `python -m py_compile lima_context.py code_orchestrator.py server.py routing_engine.py router_v3.py`
  - `python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py` -> `70 passed in 0.51s`
- Deployed `server.py`, `code_orchestrator.py`, and `lima_context.py` to VPS with backup at `/opt/lima-router/backups/context-preflight-20260522_183133`.
- Remote compile and `/health` passed after `systemctl restart lima-router`.
- Synced a no-BOM `code_orchestrator.py` copy after local cleanup with backup at `/opt/lima-router/backups/context-preflight-sync-20260522_183423`.
- Final remote compile and `/health` passed after restart.
- Final public Anthropic tool smoke returned 200 in 600ms with `stop_reason=tool_use`.

## 2026-05-22 Free Model Routing Refresh

- Checked whether all SCNet and Kimi-family free models were actually in use.
- Confirmed registration exists in `backends.py`, but routing did not actively use all working free capacity.
- Ran VPS smoke for SCNet/Kimi-family candidates:
  - Working: `scnet_ds_flash`, `scnet_ds_pro`, `scnet_qwen235b`, `scnet_qwen30b`, `cf_kimi_k26`.
  - Not production-live in smoke: `scnet_minimax`, `scnet_large_ds_flash`, `scnet_large_ds_pro`, `stock_kimi_k2`, `kimi`, `kimi_thinking`, `kimi_search`.
- Updated `code_orchestrator.py` and `router_v3.py` so VPS-working free SCNet models are active fallback capacity.
- Kept local proxy models registered but late because VPS ports `4504` and `4505` refused connections.
- Added `docs/FREE_MODEL_ROUTING_STATUS.md`.
- Added `docs/LIMA_MEMORY.md` as the detailed durable memory document.
- Local verification after route changes passed: `71 passed in 0.52s`.
- Deployed `code_orchestrator.py` and `router_v3.py` to VPS with backup at `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- `systemctl restart lima-router` initially hung because uvicorn was waiting for open connections to close; fixed by `systemctl kill -s SIGKILL lima-router`, `systemctl reset-failed lima-router`, then `systemctl start lima-router`.
- VPS `/health` returned 200 after recovery.
- Public coding smoke returned 200 in 4585ms.
- Public Anthropic tool smoke returned 200 in 672ms with `stop_reason=tool_use`.

## 2026-05-22 SCNet/Kimi First-Tier Eval

- Created `docs/superpowers/plans/2026-05-22-free-model-first-tier-eval.md`.
- Ran a VPS-side three-case coding fixture against SCNet and Kimi-family candidates.
- SCNet direct first-tier winners:
  - `scnet_ds_flash`: 3/3, avg score 100, avg latency 3330ms.
  - `scnet_qwen235b`: 3/3, avg score 100, avg latency 4004ms.
  - `scnet_qwen30b`: 3/3, avg score 91, avg latency 2713ms.
  - `scnet_ds_pro`: 3/3, avg score 91, avg latency 4571ms.
- Kimi did not meet first-tier criteria:
  - `cf_kimi_k26`: 1/3, avg score 48, avg latency 7844ms.
  - local `kimi`, `kimi_thinking`, `kimi_search`: VPS proxy `4504` refused connections.
  - `stock_kimi_k2`: invalid response.
- Updated `code_orchestrator.py` and `router_v3.py` to move direct SCNet winners into coding first tier.
- Added `data/free_model_first_tier_eval.json` with the summary evidence.
- Local verification passed after routing change: `71 passed in 0.59s`.
- Deployed `code_orchestrator.py` and `router_v3.py` to VPS with backup at `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Remote compile passed; `lima-router` restarted cleanly; VPS `/health` returned 200.
- VPS route order smoke confirmed coding selection starts with `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, then `github_gpt4o`.
- Public coding smoke returned 200 in 3347ms.

## 2026-05-22 Local Proxy And FRP Closure

- Corrected the earlier proxy diagnosis: Kimi and SCNet-large are Windows-local services, not VPS-local services.
- Updated `local_router_start.bat` so it starts `D:\GIT\server.py` on Windows port `8080` and then starts `frpc.exe` if needed.
- Verified Windows `4505` SCNet-large models and chat completion locally.
- Verified Windows `4504` Kimi models locally; chat currently fails with `chat.anonymous_usage_exceeded`, so Kimi needs session refresh.
- Verified `frpc.exe` registers `redcode-api`.
- After VPS `8088/tcp` was opened, verified public FRP path:
  - `http://47.112.162.80:8088/health`: 200.
  - `http://47.112.162.80:8088/v1/models`: 200.
  - `http://47.112.162.80:8088/v1/chat/completions`: 200.
- Added `docs/LOCAL_PROXY_RUNTIME_STATUS.md`.

## 2026-05-22 Documentation And Next Roadmap

- Updated source-of-truth docs for the personal coding assistant direction.
- Added `docs/DOCUMENTATION_STATUS.md` to mark active docs versus historical commercial/open-platform docs.
- Added `docs/FREE_WEB_AI_EXPANSION_PLAN.md` for the next phase:
  - find more no-login web AI candidates like DuckAI and HeckAI;
  - improve token/session refresh, rate limiting, and quota handling;
  - optimize routing so free backends are selected by quality, health, latency, quota, and task fit.
- Added `docs/superpowers/plans/2026-05-22-free-web-ai-stability-routing.md` as the executable Superpowers implementation plan.
- Verification:
  - `git diff --check` passed with line-ending warnings only.
  - Core suite passed with `pytest --ignore=active_model`: `66 passed, 5 skipped`.
  - Plain pytest collection is blocked by stale junction `D:\GIT\active_model`.
  - Public FRP health/models/chat smokes on `http://47.112.162.80:8088` returned 200.

## 2026-05-22 Free Web AI Sandbox Probe

- Created branch `codex/free-web-ai-probe`.
- Added candidate registry:
  - `data/free_web_ai_candidates.json`
  - `docs/free-web-ai-candidates.md`
- Added sandbox probe harness:
  - `scripts/probe_free_web_ai.py`
  - `tests/test_free_web_ai_probe.py`
- TDD verification:
  - RED: `tests/test_free_web_ai_probe.py` failed with missing `scripts.probe_free_web_ai`.
  - GREEN: `4 passed in 0.05s`.
- Reachability probe:
  - Command: `D:\GIT\venv\Scripts\python.exe scripts\probe_free_web_ai.py --timeout 20`.
  - Output: `data/free_web_ai_probe_results.json`.
  - Result: 6/6 candidate pages returned HTTP 200.
- Added failure-state classification to `health_tracker.py`.
- Updated `http_caller.py` so backend error text reaches `health_tracker.record_failure`.
- Focused verification passed: `6 passed in 0.07s` for new probe tests plus health-state tests.
- Full branch verification passed:
  - `72 passed, 5 skipped` with `pytest --ignore=active_model`.
  - JSON registry/results validation passed.
  - Probe dry-run listed six candidates.
  - FRP `/health` returned 200.

## 2026-05-22 Local Reverse AI Inventory

- Audited local ports/processes:
  - `4500` DuckAI, `4502` TheOldLLM, `4503` g4f, `4504` Kimi, `4505` SCNet-large, `8080` LiMa, `11434` Ollama.
- Verified DuckAI is already reversed in `D:\duckai`; `/v1/models` and user-only chat pass locally.
- Reproduced DuckAI LiMa-format blocker: empty OpenAI `system` message causes upstream 400.
- Verified SCNet-large `4505` models and chat pass locally.
- Verified Kimi `4504` models pass but chat returns `chat.anonymous_usage_exceeded`.
- Verified TheOldLLM `4502` models pass but local chat timed out after 30 seconds.
- Verified g4f `4503` default chat works, while one explicit PollinationsAI model mapping failed.
- Recorded inventory in:
  - `docs/LOCAL_REVERSE_AI_STATUS.md`
  - `data/local_reverse_ai_inventory.json`
  - `docs/superpowers/plans/2026-05-22-local-reverse-ai-integration.md`
- Updated candidate docs so DuckAI is no longer treated as net-new reverse work and HeckAI is marked as an existing adapter draft.

## 2026-05-22 Local Reverse AI Integration

- Added RED/GREEN coverage for OpenAI `no_system` body construction.
- Updated `http_caller.py` so DuckAI-style OpenAI backends omit `role=system` and preserve non-empty system/IDE context in the first user message.
- Marked DuckAI backends `no_system` and registered the three missing local DuckAI models.
- Kept DuckAI models late in `router_v3.py` and `code_orchestrator.py` fallback order.
- Ran DuckAI local coding admission with dedicated output:
  - `data/ddg_route_admission_eval.json`
  - `docs/DDG_ROUTE_ADMISSION.md`
  - `ddg_gpt4o_mini` and `ddg_gpt5_mini`: 3/3.
  - `ddg_claude_haiku_45`: strict JSON failure.
  - `ddg_tinfoil_gptoss_120b`: upstream 500/cooldown.
- Confirmed Kimi chat still returns `chat.anonymous_usage_exceeded` and health state is `manual_refresh_required`.
- Ran SCNet-large local route eval with dedicated output:
  - `data/scnet_large_route_eval.json`
  - `docs/SCNET_LARGE_ROUTE_EVAL.md`
  - `scnet_large_ds_flash` and `scnet_large_ds_pro`: both 3/3.
- Reproduced TheOldLLM local `4502` 30s chat timeout and left it late until refresh/log safety plus upstream diagnosis are closed.

## 2026-05-22 Claude Code LiMa Tool-Loop Incident

- Reproduced healthy baseline:
  - Claude CLI simple prompt returned `claude-cli-ok`.
  - Claude CLI `Read D:\GIT\routing_engine.py` returned `read-loop-ok`.
  - Claude CLI stream-json `Read D:\GIT\server.py` returned `read-server-ok`.
- Identified unguarded protocol boundary in `server.py`: empty or malformed OpenAI-style upstream tool responses could become Anthropic HTTP 200 responses with empty `content`.
- Added failing regression tests in `tests/test_anthropic_tool_protocol.py`; initial run failed 4/4.
- Hardened `_convert_response_openai_to_anthropic()` and simulated Anthropic SSE `tool_use` block starts.
- Verification:
  - `tests/test_anthropic_tool_protocol.py`: `4 passed`.
  - Focused suite: `90 passed, 5 skipped`.
  - VPS backup: `/opt/lima-router/backups/claude-tool-protocol-20260522_220037`.
  - VPS health: 200.
  - Public `/v1/messages`: exact `deployed-msg-ok`.
  - Real Claude CLI large-file `Read`: exact `deployed-read-ok`.
  - FRP health: 200.

## 2026-05-22 P0 Router Hardening

- Created `docs/superpowers/plans/2026-05-22-p0-router-hardening.md` before code changes.
- Added RED tests:
  - `tests/test_access_guard.py` for private key parsing, missing-auth rejection, configured-key acceptance, unconfigured fail-closed behavior, and admin fail-closed behavior.
  - `tests/test_fallback_context.py` for preserving full messages during fallback backend retries.
- Verified RED: focused run failed because `access_guard` did not exist yet.
- Implemented `access_guard.py`:
  - Reads `LIMA_API_KEY`.
  - Reads comma-separated `LIMA_API_KEYS`.
  - Accepts either `Authorization: Bearer <key>` or raw `Authorization: <key>`.
  - Fails closed with 503 if no private key is configured.
  - Returns 401 for missing or invalid authorization.
- Wired the guard into `server.py` for:
  - `/v1/chat/completions`
  - `/v1/messages`
  - `/api/live-key`
  - `/v1/status`
- Kept `/health` and `/v1/models` unauthenticated for smoke checks and IDE model discovery.
- Changed `routes/admin.py` so missing `LIMA_ADMIN_TOKEN` returns 503 instead of allowing admin access.
- Updated `_try_backend()` to accept full `messages` and changed same-tier plus upgrade fallback call sites to pass `messages_to_dicts(req.messages)`.
- Fixed `_detect_ide()` so ordinary chat messages return an empty string instead of a truthy unknown marker.
- Added `tests/test_ide_detection.py` to prevent ordinary requests from being treated as IDE traffic.
- Protected `/v1/images/generations` with the same private API key guard.
- Added `tests/test_image_endpoint_guard.py` and capped image dimensions at 2048x2048.
- Added `tests/test_stream_footer.py` with RED/GREEN coverage for Anthropic speculative and fake stream paths.
- Removed client-visible backend footers from Anthropic streaming responses; backend names stay available to internal request logging.
- Reworked `test_streaming.py` so its async generator checks run via `asyncio.run()` instead of being skipped when `pytest-asyncio` is not installed/configured.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_access_guard.py tests\test_fallback_context.py -q --ignore=active_model`: `6 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_ide_detection.py tests\test_image_endpoint_guard.py -q --ignore=active_model`: `4 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_stream_footer.py -q --ignore=active_model`: `2 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest test_streaming.py -q --ignore=active_model`: `5 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile access_guard.py server.py routes\admin.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile test_streaming.py`: passed.
  - Core suite with new tests: `112 passed`.
- Caveat:
  - This increment is local only and has not been deployed to VPS.

## 2026-05-22 Superpowers Plan Closure Review

- Reconciled historical Superpowers plan checkboxes:
  - `2026-05-22-cloudflare-workers-ai-routing.md`
  - `2026-05-22-token-safe-local-proxy-routing.md`
  - `2026-05-22-free-model-first-tier-eval.md`
- Added `docs/superpowers/PLAN_CLOSURE_STATUS.md` to classify each plan as closed, local closed, non-goal, or deferred risk.
- Current judgment:
  - Main `task_plan.md` phases are complete.
  - Historical Superpowers execution plans are checkbox-reconciled.
  - P0 router hardening was local closed at this point; it was deployed in the later explicit VPS deployment pass.

## 2026-05-22 P0 Router Hardening VPS Deployment

- Pushed commit `c4515d3` to `origin/codex/free-web-ai-probe`.
- Deployed P0 runtime files to VPS after explicit user approval:
  - `server.py`
  - `access_guard.py`
  - `routes/admin.py`
- Backup: `/opt/lima-router/backups/p0-router-hardening-20260522_230407`.
- Remote `.env` did not have `LIMA_API_KEY` or `LIMA_API_KEYS`; added `LIMA_API_KEY` so the fail-closed private guard would not break authorized IDE/API clients.
- Remote compile passed for `server.py`, `access_guard.py`, and `routes/admin.py`.
- `lima-router` restarted active.
- First smoke immediately after restart hit a short connection-refused window before uvicorn listened; follow-up service status showed the process active and listening on `0.0.0.0:8080`.
- Public authorized OpenAI and Anthropic smokes initially returned 500.
- Root cause: VPS `health_tracker.py` was stale and lacked `get_backend_state()`, while current `routing_engine.py` calls it.
- Synced `health_tracker.py`:
  - Backup: `/opt/lima-router/backups/health-tracker-sync-20260522_230937`.
  - Remote compile passed for `health_tracker.py`, `routing_engine.py`, `server.py`, `access_guard.py`, and `routes/admin.py`.
  - `lima-router` restarted active.
- Final smoke:
  - Public `/v1/chat/completions` without auth returned 401.
  - Public `/v1/chat/completions` with auth returned exact `p0-deploy-ok`.
  - Public `/v1/messages` with auth returned exact `p0-msg-ok`.
  - FRP `http://47.112.162.80:8088/health` returned 200.

## 2026-05-23 Code Quality Hardening Evidence Closure

- Closed Task 5 of `docs/superpowers/plans/2026-05-22-code-quality-correctness-hardening.md` as a documentation and evidence-only pass.
- Accepted/fixed findings:
  - `smart_router._has_vision_content` was disconnected; the `cf_vision` image path is restored and covered by `tests/test_vision_routing.py`.
  - Anthropic vision stats now measure duration from the real request start; `tests/test_request_stats.py` covers the helper and `/v1/messages` image branch.
  - `_record_request()` performs IP location lookup outside `_stats_lock`, while stats writes stay inside the lock.
  - Local one-off deploy/debug/run/stress probes are protected by root-anchored `.gitignore`; tracked `scripts/` hardcoded `sk-` literals were replaced by environment reads.
- Rejected/outdated findings:
  - Admin API routes are not unauthenticated after P0; HTML admin shell review remains separate.
  - Current `deploy_v3.py` uses `LIMA_DEPLOY_PASS` or key path, not a plaintext deploy password.
  - The old `test_streaming.py` issue is stale because P0 executed and passed it.
- Deferred follow-ups:
  - Split `server.py`.
  - Establish a `BACKENDS` single source.
  - Deduplicate response-builder logic.
  - Migrate `smart_router.cb_*` state into `health_tracker`.
- Security note: any previously exposed tokens should be rotated; no token values were copied into docs.
- Deployment policy: this round is local-only unless the user explicitly requests deploy later.
- Verification:
  - `git -C D:\GIT diff --check`: passed without whitespace errors; warning-only CRLF notices appeared for unrelated dirty files `backends.py`, `budget_manager.py`, `capability_matrix.py`, and `router_v3.py`.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile smart_router.py server.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_vision_routing.py tests\test_request_stats.py -q --ignore=active_model`: `5 passed`.
  - Core suite: `117 passed`.
  - `git -C D:\GIT grep -n "sk-" -- scripts`: no output, expected for no matches.

Follow-up after final review:

- Final reviewer found that the initial script scrub only covered `sk-` token shapes and missed non-`sk` OneAPI/admin/provider credential literals in tracked `scripts/`.
- Commit `e231a5e chore: remove remaining script credentials` moved those remaining tracked script credentials to environment-variable reads.
- Sanitized broader tracked-script scans passed without hardcoded credential literals, and `D:\GIT\venv\Scripts\python.exe -m compileall -q scripts` passed.
- Credentials that appeared in history still require rotation outside Git.

## 2026-05-23 Documentation Calibration And Reference Review

- Re-read the LiMa active code and source-of-truth docs after the latest hardening commits.
- Confirmed current branch `codex/free-web-ai-probe` and latest checked commit `8b86228`.
- Re-ran the LiMa target test suite:
  - `python -m pytest -q tests .\test_routing_engine.py .\test_rate_limiter.py .\test_http_caller.py .\test_dual_track.py .\test_code_orchestrator.py .\test_streaming.py .\test_skills_injector.py --ignore=active_model`
  - Result: `382 passed, 8 skipped`.
- Calibrated module status at that time, superseded by later 2026-05-24 closure records:
  - Session Memory writes and compaction trigger are in the successful chat path.
  - Session Memory recall processor exists but is not the main `server.py` prompt-time path.
  - Graph retrieval/reranking was still compute-only at that time; later 2026-05-24 work closed this gap through `inject_retrieval_context()`.
  - Tool Gateway executor is hardened with `shell=False`, audit events, and copied HTTP args.
  - Admin UI auth is improved, but query-token login remains a later hardening target.
  - `ConcurrencyPool` existed and was tested, but key scheduling had not been replaced at that time; later 2026-05-24 work wired `key_pool.py` into `http_caller.py`.
- Reviewed external references:
  - OpenRAG is valuable for knowledge ingestion, retrieval traceability, MCP knowledge tools, and document parsing patterns.
  - Google Cloud always-on-memory-agent is the stronger near-term reference for LiMa's memory daemon and consolidation layer.
- Added `docs/REFERENCE_PROJECT_EVALUATION.md`.
- Updated active docs to point the next architecture step toward retrieval injection plus always-on typed memory rather than adding another large platform.

## 2026-05-23 Agent Autonomy Plan

- Created `docs/superpowers/plans/2026-05-23-agent-autonomy-evolution.md` as the Superpowers implementation plan for gated LiMa autonomy.
- The plan evaluates OpenAI Agents SDK, Google ADK, GenericAgent, EvoMap Evolver, and Agency Agents against LiMa's current private coding-assistant architecture.
- Recommended sequence:
  - Retrieval and typed memory evidence before agents.
  - Agent workbench ledger before autonomous loops.
  - Five-agent local loop before any large persona library.
  - Skill/gene memory only after successful validated tasks.
  - GitHub/VPS operations behind explicit approval gates.
- Updated `docs/DOCUMENTATION_STATUS.md` to point to the new active plan.
- Added agent-reference findings to `findings.md`.
- No runtime code was changed in this pass.

## 2026-05-23 TechSpar Mastery Loop Plan

- Reviewed TechSpar as a reference for LiMa's evidence-driven improvement loop.
- Created `docs/superpowers/plans/2026-05-23-techspar-mastery-loop.md`.
- Positioned TechSpar as a mastery/profile/scheduling reference, not an agent runtime framework.
- Recommended a future `mastery_loop/` layer:
  - event adapters;
  - scoring;
  - weak-point extraction;
  - SQLite profile store;
  - SM-2-inspired review scheduling;
  - planner/tester recommendations;
  - admin trace.
- Updated `docs/DOCUMENTATION_STATUS.md` and `findings.md`.
- No runtime code was changed in this pass.

## 2026-05-23 LiMa Code Fork Start

- Owner forked LiMa Code to `https://github.com/zhuguang-ZFG/deepcode-cli.git`.
- Created `docs/superpowers/plans/2026-05-23-lima-code-vibe-coding.md`.
- Updated `docs/DOCUMENTATION_STATUS.md` and `findings.md`.
- First attempted network reachability to the fork failed from the sandboxed command environment with inability to connect to `github.com:443`; next step is to retry clone with approved network access.
- Retried with approved network access and cloned the fork into `D:\GIT\deepcode-cli`.
- Read LiMa Code `AGENTS.md`, `package.json`, README, configuration docs, provider settings, OpenAI client setup, tool executor, and bash handler.
- Confirmed LiMa Code is TypeScript/npm, OpenAI-compatible through `MODEL`, `BASE_URL`, and `API_KEY`, and has real local tool execution through `bash`.
- Added first LiMa Code fork changes:
  - `D:\GIT\deepcode-cli\docs\lima.md`
  - `D:\GIT\deepcode-cli\docs\lima_zh_CN.md`
  - README links in `README-en.md`, `README.md`, and `README-zh_CN.md`.
- LiMa Code validation:
  - `git -C D:\GIT\deepcode-cli diff --check`: passed.
  - Secret-shape scan over the new LiMa docs: no matches.
- Did not install npm dependencies or run `npm test` yet because this first change is documentation/config guidance only.
- No LiMa runtime code was changed in this pass.

## 2026-05-23 LiMa Code Rebrand Slice

- Renamed the active Superpowers plan to `docs/superpowers/plans/2026-05-23-lima-code-vibe-coding.md`.
- Rebranded the fork's user-facing product surface to LiMa Code:
  - npm package name: `lima-code`;
  - CLI bin: `lima-code`;
  - CLI help, TTY errors, update prompt, welcome screen, slash-command exit text, system prompt identity, MCP client name, and checkpoint author.
- Updated README and docs to promote `lima-code`.
- Kept `.deepcode` paths and `DEEPCODE_*` environment variables as a legacy compatibility layer for this first slice.
- No LiMa runtime code or VPS files were changed.

## 2026-05-23 LiMa Code Native Config Slice

- Added native LiMa Code config support in the fork:
  - `~/.lima-code/settings.json` and `<project>/.lima-code/settings.json` are preferred.
  - Legacy `~/.deepcode/settings.json` and `<project>/.deepcode/settings.json` remain readable fallbacks.
  - `LIMA_CODE_*` environment variables are preferred over legacy `DEEPCODE_*` variables.
  - `DEEPCODE_*` remains a fallback for old local profiles.
  - Model-selection writes create `.lima-code` settings by default, but update an existing project `.deepcode/settings.json` when that is the only project config.
- Updated CLI help, API-key error text, WebSearch config error text, README files, LiMa provider docs, MCP docs, notification docs, and configuration docs to promote `.lima-code` / `LIMA_CODE_*`.
- Added regression tests:
  - `D:\GIT\deepcode-cli\src\tests\app-settings-paths.test.ts`
  - expanded `D:\GIT\deepcode-cli\src\tests\settings-and-notify.test.ts`
  - updated `D:\GIT\deepcode-cli\src\tests\web-search-handler.test.ts`
- No LiMa runtime code or VPS files were changed.

## 2026-05-23 Agent Evolution Implementation

- Executed `docs/superpowers/plans/2026-05-23-lima-server-agent-evolution.md` (6 phases).
- **Phase 0: Quality Gates** — Fixed 7 review findings (P1/P2/P3), added typed memory validation, 60 regression tests.
- **Phase 1: Worker Contract** — `agent_contracts/task_contract.py` with AgentTaskRequest/Result schemas (12 tests).
- **Phase 2: Agent Role Layer** — 7 roles with permission gating, only `coder` can modify code (12 tests).
- **Phase 3: Evaluation Harness** — TaskScore, EvalResult, can_auto_promote() gate (6 tests).
- **Phase 4: Evolution Loop** — CandidateSkill extraction + dual-gate promotion (5 tests).
- **Phase 5: Server APIs** — 5 protected endpoints under `/agent/` (8 tests).
- **Total: 103 tests passing.** Server never executes shell; evolution is eval-gated + manually promoted.

## 2026-05-23 LiMa Code Worker Command Runner

- Added a real local command runner for LiMa Code:
  - `/lima connect` reports local Server configuration without exposing keys.
  - `/lima status` reports project and Server configuration state.
  - `/lima review` runs guarded local review mode over the current git diff.
  - `/lima task <task_id>` fetches a LiMa Server task, runs the guarded local task runner, writes local audit evidence, and submits the structured result back to Server.
- Wired the UI path so `/lima task <id>` is handled locally instead of being sent to the model as a chat prompt.
- Added `src/tests/lima-command-runner.test.ts`.
- Fixed Windows Bash timeout cleanup: after killing the process tree, LiMa Code now waits for process close before returning, preventing temp workspace `EPERM` cleanup failures while still ignoring post-timeout output.
- Added `.lima-code/` to LiMa Code `.gitignore` because local audit/settings data may contain sensitive runtime state.
- Public end-to-end smoke:
  - Created LiMa Server task `4d6c02b3` through `https://chat.donglicao.com/agent/tasks`.
  - Ran LiMa Code `/lima task 4d6c02b3` locally against `D:\GIT\deepcode-cli`.
  - Worker returned `needs_review`, listed `src/ui/App.tsx` and `src/ui/PromptInput.tsx`, and submitted the result.
  - Server detail confirmed `hasResult=true`; events endpoint returned `created,result_submitted`.
- Verification:
  - LiMa targeted tests: `41 passed`.
  - Tool handler regression tests: `22 passed`.
  - `npm.cmd run check`: passed.
  - Full LiMa Code suite: `368 passed, 7 skipped`.

## 2026-05-23 LiMa Code Single-Claim Worker

- Added `/lima next` to LiMa Code.
- `/lima next` claims the first pending `accepted` LiMa Server task through `GET /agent/tasks?status=accepted&limit=1`, runs it through the guarded local task runner, writes local audit evidence, and submits the result.
- If no pending task exists, it exits cleanly with a no-task message.
- Kept this as a single-task command; a daemon/poll loop remains a later explicit phase with backoff and stop controls.
- Public end-to-end smoke:
  - Created Server task `eb9410e1`.
  - Ran LiMa Code `/lima next` against `https://chat.donglicao.com`.
  - Worker returned `needs_review` and submitted the result.
  - Server detail confirmed `hasResult=true`; events endpoint returned `created,result_submitted`.
- Verification:
  - Parser/runner tests: `13 passed`.
  - LiMa worker targeted tests: `52 passed`.
  - `npm.cmd run check`: passed.
  - Full LiMa Code suite: `371 passed, 7 skipped`.

## 2026-05-23 LiMa Code Bounded Worker Loop

- Added `/lima work --once` and `/lima work --loop --max-tasks <n>`.
- Loop mode requires `--max-tasks` and caps it at 100 to avoid uncontrolled background execution.
- Defaults:
  - `--interval-ms`: `5000`
  - `--backoff-ms`: `30000`
- Loop stops when:
  - no pending task exists;
  - `maxTasks` is reached;
  - a task/fetch/submit failure occurs;
  - UI abort signal fires.
- Wired UI Ctrl+C/Esc to abort active LiMa worker commands through `AbortController`.
- Public smoke was intentionally run against a temporary empty directory instead of the real repo to avoid uploading local diff content:
  - Created Server tasks `3428f2b5` and `ae549d08`.
  - Ran `/lima work --loop --max-tasks 2 --interval-ms 1`.
  - Both tasks submitted `needs_review`.
  - Both event streams returned `created,result_submitted`.
  - `changedFileCount=0`.
- Verification:
  - Parser/runner tests: `19 passed`.
  - LiMa worker targeted tests: `58 passed`.
  - `npm.cmd run check`: passed.
  - Full LiMa Code suite: `377 passed, 7 skipped`.

## 2026-05-23 LiMa Autonomous Worker v0.2 Plan

- Added `docs/superpowers/plans/2026-05-23-lima-autonomous-worker-v02.md`.
- The plan explicitly follows the GenericAgent/Evolver/agency-agents direction as controlled autonomy:
  - GenericAgent-style repeated success becomes candidate skills.
  - Evolver-style self-improvement becomes evidence-gated promotion.
  - agency-agents-style roles remain a compact coding role set.
- The plan keeps LiMa Server as orchestrator and audit gate, and LiMa Code as the local allowlisted executor.
- Scope before real daemon mode:
  - Server claim/cancel/control/review/quarantine endpoints.
  - LiMa Code repo allowlist, worker budget, failure quarantine, stop marker, and audit command.
  - Safe temporary real-repo smoke for patch plus test plus result submission.
- This is design-only; no runtime code was changed in this entry.

## 2026-05-23 KERNEL Prompt Contract Todo

- Recorded KERNEL as a future `LiMa Task Prompt Contract v0.1` item in `task_plan.md`.
- Intended use:
  - Normalize Server-created agent tasks with `Context`, `Task`, `Constraints`, `Verify`, and `Output`.
  - Keep LiMa Code worker tasks single-purpose and easy to verify.
  - Reduce prompt drift during candidate skill extraction and evolution review.
- Source reference: Reddit PromptEngineering KERNEL framework post shared by the user.
- This is a todo only; no runtime code was changed.

## 2026-05-23 Claude Code Infrastructure Todo

- Recorded `LiMa Code Hooks + Skill Auto-Activation v0.1` as a future item in `task_plan.md`.
- Source reference: the Claude Code infrastructure tips thread and `diet103/claude-code-infrastructure-showcase`.
- Intended use after autonomous worker v0.2 lifecycle controls:
  - Skill auto-activation rules based on prompt, file path, and content patterns.
  - Post-task, post-edit, and stop checkpoints for touched files, tests, failures, and review gates.
  - Worker-local dev docs under `.lima-code/dev/active/<task>/plan.md`, `context.md`, and `tasks.md`.
  - `/lima docs` and `/lima docs-update` commands.
  - Final worker summaries that explicitly list changed files, tests run, remaining risks, and review status.
- This is a todo only; no runtime code was changed.

## 2026-05-23 Parlant Policy Guidelines Todo

- Recorded `LiMa Policy Guidelines Engine v0.1` as a future item in `task_plan.md`.
- Source reference: `emcie-co/parlant`.
- Intended use after hooks and skill auto-activation:
  - Condition-action guidelines for task policy, role activation, tool permission, and review gates.
  - Dependencies and exclusions between guidelines so incompatible modes cannot activate together.
  - Journey-style mapping to LiMa task lifecycle states.
  - Tool activation only when observations match task policy.
  - Explainability traces for why a guideline, skill, role, or tool was activated.
- This is a todo only; no runtime code was changed.

## 2026-05-23 Autonomous Worker v0.2 Task 1

- Implemented the shared agent task lifecycle contract on Server and LiMa Code.
- Server `AgentTaskResult` now accepts lifecycle statuses: `claimed`, `approved`, `rejected`, `applied`, `cancel_requested`, `cancelled`, and `quarantined`.
- Server `AgentTaskRequest` now carries worker lifecycle metadata: `worker_id`, `lease_expires_at`, `cancel_requested`, and `failure_count`.
- LiMa Code TypeScript validation accepts the same statuses and optional metadata.
- Red-green evidence:
  - Server contract tests first failed on missing lifecycle metadata/statuses.
  - LiMa Code contract tests first failed on stripped metadata and missing statuses.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py -q --ignore=active_model`: `14 passed`.
  - `npm.cmd test -- src/tests/lima-agent-task-types.test.ts`: `380 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 2

- Implemented Server-side lifecycle gates for agent tasks.
- Added `/agent/tasks/{task_id}/claim` to assign `worker_id`, lease expiry, and transition the task to `running`.
- Added `/agent/tasks/{task_id}/cancel` and `/agent/tasks/{task_id}/control` so workers can observe cancellation state.
- Added `/agent/tasks/{task_id}/review` as the human review gate from `needs_review` to `approved` or `rejected`.
- Task result body validation now accepts the full lifecycle status set from the shared contract.
- `_append_event()` now keeps task envelopes and event streams aligned.
- Red-green evidence:
  - Route tests first failed with 404 for missing `claim`, `cancel`, and `review` endpoints.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_routes.py tests\test_agent_evolution.py -q --ignore=active_model`: `19 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py -q --ignore=active_model`: `14 passed`.

## 2026-05-23 Autonomous Worker v0.2 Task 3

- Implemented explicit LiMa Code repository allowlisting.
- Added `src/lima/repo-allowlist.ts` so the current workspace is allowed by default and sibling repositories require explicit `allowedRepos` configuration.
- Wired `workspace-guard.ts` to use the allowlist while preserving existing `allowedRoots` compatibility.
- Red-green evidence:
  - `npm.cmd test -- src/tests/lima-repo-allowlist.test.ts` first failed because `repo-allowlist.ts` did not exist.
- Verification:
  - `npm.cmd test -- src/tests/lima-repo-allowlist.test.ts src/tests/lima-workspace-guard.test.ts`: `385 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 4

- Implemented LiMa Code worker-session budgets.
- Added `src/lima/worker-budget.ts` to stop worker loops by max task count or max elapsed minutes.
- Added `/lima work --max-minutes <n>` parsing with a default 60-minute session budget.
- Wired the work loop to check budget before fetching the next task and to report the budget stop reason.
- Red-green evidence:
  - Budget tests first failed because `worker-budget.ts` did not exist.
  - Command tests first failed because `/lima work` did not carry `maxMinutes`.
  - Work-loop test first failed because the loop processed a second task after the time budget was exceeded.
- Verification:
  - `npm.cmd test -- src/tests/lima-worker-budget.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts`: `391 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 5

- Implemented repeated-failure quarantine for LiMa Code worker tasks.
- Added `.lima-code/quarantine.json` state management through `src/lima/failure-quarantine.ts`.
- Added `LiMaAgentTaskClient.quarantineTask()` for `POST /agent/tasks/{task_id}/quarantine`.
- Wired worker loop failures so a task reaching 3 recorded failures is reported to Server as `quarantined`.
- Added Server `/agent/tasks/{task_id}/quarantine` endpoint and event emission.
- Red-green evidence:
  - Server route test first failed with `404` for the missing quarantine endpoint.
  - LiMa Code client test first failed because `quarantineTask` did not exist.
  - LiMa Code quarantine tests first failed because `failure-quarantine.ts` did not exist.
  - Worker loop test first failed because repeated failures were not quarantined.
- Verification:
  - `npm.cmd test -- src/tests/lima-failure-quarantine.test.ts src/tests/lima-agent-task-client.test.ts src/tests/lima-command-runner.test.ts`: `395 passed, 6 skipped`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_routes.py -q --ignore=active_model`: `15 passed`.
  - `npm.cmd run check`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile routes\agent_tasks.py`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 6

- Implemented LiMa Code worker stop control.
- Added `.lima-code/worker.stop.json` marker helpers in `src/lima/worker-control.ts`.
- Added `/lima daemon status` and `/lima daemon stop` commands.
- Wired the work loop to stop before fetching another task when the stop marker is present.
- Red-green evidence:
  - Command tests first failed because `/lima daemon` was not parsed.
  - Worker-control tests first failed because `worker-control.ts` did not exist.
  - Work-loop test first failed because `fetchPendingTask` still ran even with a stop marker.
- Verification:
  - `npm.cmd test -- src/tests/lima-worker-control.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts`: `400 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 7

- Implemented LiMa Code audit viewing.
- Added `src/lima/audit-reader.ts` to read `.lima-code/audit.jsonl`, normalize `timestamp` and `created_at`, sort newest first, and format a compact summary.
- Added `/lima audit [--last <n>]` command parsing and runner output.
- Red-green evidence:
  - Audit reader tests first failed because `audit-reader.ts` did not exist.
  - Command tests first failed because `/lima audit` was not parsed.
  - Runner test first failed because audit commands returned usage text instead of audit entries.
- Verification:
  - `npm.cmd test -- src/tests/lima-audit-reader.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts`: `405 passed, 6 skipped`.
  - `npm.cmd run check`: passed.

## 2026-05-23 Autonomous Worker v0.2 Task 8

- Added a real temporary git repository smoke test for LiMa Code patch mode.
- Patch mode now runs explicit `test_commands` after applying `patch_files` when the task allows the `test` tool.
- The submitted result now includes changed files, diff preview, test commands, and test results for patch-plus-test tasks.
- Closed an end-to-end contract gap found during smoke work:
  - Server `AgentTaskRequest` accepts `patch_files` and `test_commands`.
  - Server `/agent/tasks` preserves those fields in fetched task envelopes.
  - LiMa Code request validation preserves those fields instead of stripping them.
- Red-green evidence:
  - The local smoke first failed because patch mode submitted no test evidence.
  - Server contract tests first failed on missing `patch_files` support.
  - LiMa Code validation tests first failed because `patch_files` were stripped.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py tests\test_agent_task_routes.py -q --ignore=active_model`: `31 passed`.
  - `npm.cmd test -- src/tests/lima-agent-task-types.test.ts src/tests/lima-command-runner.test.ts`: `407 passed, 6 skipped`.
  - `npm.cmd run check`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile agent_contracts\task_contract.py routes\agent_tasks.py`: passed.
- VPS public smoke is still pending until this Server contract update is deployed. Do not treat patch-plus-test as live-verified until the VPS task endpoint returns `patch_files` and LiMa Code submits one passing `test_results` entry from a temporary repo.

Verification note:

- `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py tests\test_agent_task_routes.py tests\test_agent_evolution.py -q --ignore=active_model` currently fails in `tests/test_agent_evolution.py::test_candidate_eval_passed_no_manual_flag_cannot_promote`.
- That failure is tied to the pre-existing dirty `agent_evolution/promote.py` worktree change and was not modified in this task.

## 2026-05-23 Code Quality Review Closeout

- Added `docs/superpowers/plans/2026-05-23-code-quality-review-closeout.md` as the durable Superpowers-style record for the review findings.
- Classified the current highest-priority issues as:
  - P0: full pytest collection is broken because `tests/test_agent_task_routes.py` imports stale `_events/_tasks` symbols.
  - P0: agent task claim can overwrite an active running worker lease.
  - P0: admin UI still exposes the long-lived admin token through query-token login and JavaScript injection.
  - P1: `/v1/models` auth policy needs an explicit decision.
  - P1: backend capability config and retrieval injection have duplication/drift.
  - P2: large hot-path files and dirty worktree hygiene remain maintenance risks.
- No production deployment was performed for this review pass.
- Verification evidence:
  - `python -m py_compile server.py routing_engine.py router_v3.py http_caller.py code_orchestrator.py routes\agent_tasks.py routes\admin.py routes\telegram.py tool_gateway\executor.py`: passed.
  - `python -m pytest -q --ignore=active_model`: failed during collection with `ImportError: cannot import name '_events' from 'routes.agent_tasks'`.

## 2026-05-23 Code Quality P0 Implementation Pass

- Restored the agent task route tests to the current SQLite-backed task store by adding `_reset_for_tests()` and removing stale `_events/_tasks` imports.
- Hardened `/agent/tasks/{task_id}/claim`:
  - active `claimed` or `running` leases now return 409 instead of being overwritten;
  - expired leases can be reclaimed by another worker;
  - claim updates task state and claim events under the store lock.
- Hardened the admin HTML shell:
  - query-token URLs no longer authenticate;
  - login sets a signed HttpOnly Secure session cookie derived from `LIMA_ADMIN_TOKEN`;
  - rendered admin HTML no longer injects the raw admin token or `const _ADMIN_TOKEN`.
- Verification:
  - `python -m pytest tests\test_agent_task_routes.py tests\test_agent_task_contract.py tests\test_access_guard.py -q --ignore=active_model`: `40 passed`.
  - `python -m py_compile routes\agent_tasks.py routes\admin.py tests\test_agent_task_routes.py tests\test_access_guard.py`: passed.
  - `git diff --check` for the touched files: passed, with line-ending warnings only.
  - `python -m pytest -q --ignore=active_model`: collection now succeeds; result is `345 passed, 8 failed, 8 skipped`.
- Remaining full-suite failures are outside this P0 slice: request stats lock expectation, stream footer tests expecting removed server helpers/behavior, and Telegram bot env/mock tests.
- No production deployment was performed.

## 2026-05-23 Continued Code Review Pass

- Continued review over tracked LiMa Python code and tests, excluding untracked reference repositories and local experiments.
- Fixed the remaining full-suite failures from the previous pass:
  - request stats tests now patch `routes.request_tracking`, the actual owner of request tracking state;
  - stream footer tests now patch `routes.anthropic_stream`, the actual owner of Anthropic streaming;
  - `telegram_bot.py` reads `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `GFW_PROXY` at call time instead of freezing them at import time.
- Rewrote `routes/images.py` to remove mojibake and use explicit `[\u4e00-\u9fff]` Chinese prompt detection.
- Added image endpoint regression coverage proving Chinese prompts receive the quality prefix in the generated Pollinations URL.
- Broad tracked-Python compile verification passed for 215 files.
- Verification:
  - `python -m pytest tests\test_image_endpoint_guard.py tests\test_request_stats.py tests\test_stream_footer.py tests\test_telegram_bot.py -q --ignore=active_model`: `20 passed`.
  - `python -m pytest -q --ignore=active_model`: `354 passed, 8 skipped`.
- Remaining non-failing cleanup:
  - `routes/telegram.py` uses deprecated FastAPI startup event wiring.
  - Telegram notify tests produce coroutine-not-awaited warnings when fire-and-forget is mocked.
  - Hot-path files remain oversized relative to the 300-line project target.
- No production deployment was performed.

## 2026-05-23 LiMa Server Control Plane v0.3

- Implemented the Server control-plane v0.3 plan locally.
- Agent task contract:
  - `AgentTaskResult.status` annotation now covers every `VALID_STATUSES` lifecycle value.
- Agent audit:
  - Added `/agent/audit` with bounded task summaries and no `diff_preview`.
  - Added protected `/admin/api/agent-audit`.
  - Added a minimal Agent Tasks audit panel to the admin HTML shell.
- Telegram review preparation:
  - Added `telegram_bot.parse_approval_callback()` for `approve:<task_id>` and `reject:<task_id>`.
  - Added `routes.agent_tasks.apply_task_review()` and made the HTTP review route use it.
- Candidate evolution:
  - Added candidate extraction from approved task evidence.
  - Approved `needs_review` results now create inactive candidate skills and record candidate creation events.
  - Promotion remains gated by eval pass plus manual flag.
- Contract smoke:
  - Added `scripts/smoke_agent_task_contract.py --dry-run`.
  - The script builds and validates matching Server task/result payloads without contacting a live Server.
- Verification:
  - `python -m py_compile agent_contracts\task_contract.py routes\agent_tasks.py routes\admin.py telegram_bot.py agent_evolution\candidates.py scripts\smoke_agent_task_contract.py`: passed.
  - `python -m pytest tests\test_agent_task_contract.py tests\test_agent_task_routes.py tests\test_agent_evolution.py tests\test_telegram_bot.py tests\test_admin_agent_audit.py tests\test_agent_task_smoke_script.py -q --ignore=active_model`: `60 passed, 3 warnings`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py -q --ignore=active_model`: failed before collection because the venv lacks `pytest_asyncio`.
- Remaining warning cleanup:
  - Telegram notify tests still emit coroutine-not-awaited warnings when `_fire_and_forget` is mocked.
  - `routes/telegram.py` still uses FastAPI deprecated startup event wiring.
- No production deployment was performed.

## 2026-05-23 LiMa Real-Machine Worker Smoke v0.4

- Implemented the Server-side real-machine worker smoke plan locally.
- Added `/agent/worker/preflight`:
  - requires admin auth;
  - returns readiness, contract version, task counts, latest task id, and feature flags;
  - does not expose admin token values.
- Added `/agent/worker/smoke-task`:
  - default task is read-only `review` mode with `allowed_tools=["git_diff"]`;
  - `patch_readme` task is explicit, bounded to `README.md`, and runs only `node --version`;
  - Server still only creates task records and does not execute shell or mutate repositories.
- Added `scripts/create_lima_smoke_task.py`:
  - `--dry-run` prints only `/agent/worker/smoke-task` payload shape;
  - live mode reads `LIMA_CODE_SERVER_URL` and `LIMA_CODE_API_KEY` or CLI args;
  - output never prints API keys.
- Added `docs/LIMA_REAL_MACHINE_SMOKE.md` with `/lima doctor` as the first LiMa Code step.
- Verification:
  - `python -m pytest tests\test_agent_task_routes.py -q --ignore=active_model`: `24 passed`.
  - `python -m pytest tests\test_lima_smoke_task_script.py -q --ignore=active_model`: `2 passed`.
  - `python -m py_compile routes\agent_tasks.py tests\test_agent_task_routes.py scripts\create_lima_smoke_task.py tests\test_lima_smoke_task_script.py`: passed.
  - `Select-String -Path docs\LIMA_REAL_MACHINE_SMOKE.md -Pattern "zhuguang110|sk-|Bearer |query-token"`: no matches.
- Environment note:
  - `D:\GIT\venv\Scripts\python.exe -m pytest ...` still fails before collection because the venv lacks `pytest_asyncio`; system `python` was used for meaningful test evidence.
- No production deployment was performed.

## 2026-05-23 Web-Reverse Model Admission Batch

- Added a dedicated web-reverse/local-proxy admission path instead of directly promoting every web adapter into hot IDE routes.
- Added `web_reverse_eval.py`:
  - discovers registered web-reverse candidates from `data/local_reverse_ai_inventory.json` plus registry-only `localhost:45xx` web proxies;
  - uses synthetic public coding prompts only;
  - writes evidence-backed route promotion recommendations;
  - requires a full three-case batch before emitting route-candidate recommendations.
- Added `scripts/eval_web_reverse_models.py` with dry-run, explicit backend selection, JSON/Markdown outputs, and `--timeout-cap` for broad smoke batches.
- Added `tests/test_web_reverse_eval.py`.
- Full 29-backend smoke used only the public `public_python_bugfix` fixture:
  - passing: `scnet_large_ds_flash`, `scnet_large_ds_pro`, `kimi`, `kimi_thinking`, `kimi_search`, `longcat_web`, `longcat_web_research`;
  - DDG returned HTTP 530;
  - OldLLM returned HTTP 502;
  - `longcat_web_think` returned malformed/non-code output for the public Python fixture;
  - MiMo web is now correctly classified as cookie/auth failure, not JSON adapter failure.
- Phase 2 three-case eval:
  - `scnet_large_ds_flash`: `code_medium_candidate`, 3/3, avg 2363ms;
  - `scnet_large_ds_pro`: `code_medium_candidate`, 3/3, avg 3986ms;
  - `kimi`, `kimi_thinking`, `kimi_search`: `code_floor_candidate`, 2/3 each, failing strict JSON tool output;
  - `longcat_web`: `code_floor_candidate`, 2/3, failing strict JSON tool output;
  - `longcat_web_research`: not a coding route candidate in the current fixture set.
- Evidence files:
  - `data/web_reverse_model_smoke.json`
  - `docs/WEB_REVERSE_MODEL_SMOKE.md`
  - `data/web_reverse_model_eval.json`
  - `docs/WEB_REVERSE_MODEL_EVAL.md`
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile web_reverse_eval.py scripts\eval_web_reverse_models.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_web_reverse_eval.py -q --ignore=active_model`: `9 passed`.
  - `D:\GIT\venv\Scripts\python.exe scripts\eval_web_reverse_models.py --dry-run --timeout-cap 15`: listed 29 candidates without network calls.
- Environment note: installed missing `pytest-asyncio` into the local venv so the repo's existing `tests/conftest.py` can load.
- No production deployment was performed.

## 2026-05-23 Web-Reverse Non-JSON Adapter Fix

- Root cause:
  - LongCat/MiMo web proxies default `/v1/chat/completions` to `stream=True`.
  - LiMa non-stream `http_caller.call_api()` omitted `stream:false`, so these proxies returned SSE.
  - `call_api()` then tried to parse the SSE body as JSON and raised `Expecting value`.
- Fix:
  - Added `force_stream_param` support in `http_caller._build_body()`.
  - Set `force_stream_param: True` for `longcat_web`, `longcat_web_think`, `longcat_web_research`, `mimo_web`, `mimo_web_think`, and `mimo_web_flash`.
  - Added web-proxy control error markers to `response_cleaner`.
  - Added ASCII control-error strings in local `mimo_web_proxy.py` and `longcat_web_proxy.py` for future clean reports after proxy restart.
  - Added regression coverage in `test_http_caller.py` and `tests/test_web_reverse_eval.py`.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile http_caller.py backends.py response_cleaner.py web_reverse_eval.py scripts\eval_web_reverse_models.py test_http_caller.py tests\test_web_reverse_eval.py mimo_web_proxy.py longcat_web_proxy.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest test_http_caller.py tests\test_web_reverse_eval.py -q --ignore=active_model`: `42 passed`.
  - `D:\GIT\venv\Scripts\python.exe scripts\eval_web_reverse_models.py --max-cases 1 --timeout-cap 12 ...`: refreshed 29-candidate smoke.
  - `D:\GIT\venv\Scripts\python.exe scripts\eval_web_reverse_models.py --backends scnet_large_ds_flash,scnet_large_ds_pro,kimi,kimi_thinking,kimi_search,longcat_web,longcat_web_research ...`: refreshed phase 2 eval.
- Current conclusion:
  - LongCat non-stream adapter path is fixed; `longcat_web` is now a `code_floor_candidate`.
  - MiMo adapter path is fixed enough to classify the real blocker: expired local cookie. Refresh/restart MiMo proxy before retesting.
- No production deployment was performed.

## 2026-05-23 Memory Daemon Closeout

- Closed the gap where documentation described Session Memory as request-path-only:
  - `server.py` already starts `session_memory.daemon` during FastAPI lifespan.
  - This round added lifecycle state, idempotent start, async stop/cancel, status reporting, dynamic env config, and a single-cycle runner.
- Added `scripts/memory_daemon_ctl.py`:
  - `status` prints daemon config/status as JSON.
  - `run-once` ingests `LIMA_MEMORY_INBOX` and consolidates sessions once outside `/v1/chat/completions`.
- Added tests proving:
  - inbox ingestion archives processed files and writes typed memories;
  - consolidation can run through `run_once(ingest=False, consolidate=True)` without a request;
  - `start_daemon()` is idempotent and `stop_daemon()` cancels the tracked task;
  - CLI `status` and `run-once` output JSON.
- Updated `STATUS.md`, `docs/LIMA_MEMORY.md`, and `docs/PERSONAL_CODING_ASSISTANT_PLAN.md`.
- Remaining memory work after this daemon closeout was prompt-time recall; that is closed in the next section.
- No VPS deployment was performed in this local closeout.

## 2026-05-23 Prompt-Time Memory Recall

- Added `session_memory/prompt_recall.py` as the server-facing recall integration layer.
- `server.py` now runs prompt-time memory recall after trace creation and before token budget checks, user-identity adaptation, `smart_router.analyze()`, non-streaming `v3_route()`, OpenAI streaming, and fallback retry messages.
- The post-response SQLite write now uses the same header-derived memory session id when prompt recall is active, so future recall reads the same session that successful responses write.
- Trace/response evidence is metadata-only:
  - trace span: `prompt_memory_recall`;
  - OpenAI response meta: `x_lima_meta.memory_recall`;
  - recalled memory text is not copied into trace metadata.
- Added `tests/test_prompt_memory_recall.py`.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile session_memory\prompt_recall.py server.py tests\test_prompt_memory_recall.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_prompt_memory_recall.py tests\test_session_memory.py tests\test_compactor.py tests\test_typed_memory.py -q --ignore=active_model`: `34 passed`.
  - Extended server regression with Anthropic protocol, fallback context, and streaming tests: `44 passed`.
  - `git diff --check`: passed with CRLF warnings only.
- No production deployment was performed.

## 2026-05-23 Global Code Quality Hardening

- Fixed admin auth import-order determinism by moving current-token decisions to runtime lookup and then extracting admin auth helpers.
- Removed hardcoded runtime secret literals from active runtime files and quarantined local-only MiMo TTS/debug script risk.
- Made web-reverse admission explicit in backend metadata and docs.
- Consolidated `routing_engine.route()` retrieval injection onto the shared `inject_retrieval_context()` path.
- Split admin agent audit into `routes/admin_agent_audit.py`.
- Extracted server prompt-context staging into `server_context.py`.
- Replaced Telegram router startup `on_event` with explicit lifespan startup and removed Telegram notify coroutine-not-awaited warnings.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m compileall -q server.py routing_engine.py router_v3.py http_caller.py backends.py response_cleaner.py context_pipeline session_memory routes tool_gateway scripts tests`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest -q --ignore=active_model`: `391 passed, 8 skipped`.
  - `git diff --check`: passed with CRLF warnings only.
- No production deployment was performed.

## 2026-05-23 Global Code Quality Follow-up P1

- Closed the remaining P1 blockers from the post-hardening review:
  - updated prompt tests for the new LiMa chat identity wording;
  - removed `mimo_web*` from default IDE/chat route pools while retaining sandbox-only backend metadata;
  - removed the untracked `fc_caller` dependency from the core `routing_engine.route()` path by restoring the committed route implementation and adding a regression test;
  - tracked `session_memory/prompt_recall.py` and added a repo-manifest regression;
  - narrowed response identity cleaning so normal third-party facts such as OpenAI/ChatGPT history are preserved.
- Verification:
  - Focused follow-up suite: `37 passed`.
  - `compileall` over runtime, routes, tools, scripts, and tests: passed.
  - Full pytest: `393 passed, 8 skipped`.
- No production deployment was performed.

## 2026-05-24 Chat Model Extraction Deploy

- Added regression contract `tests/test_chat_models.py`.
- Extracted `Message`, `ChatRequest`, and `extract_system_prompt` from `server.py` into `chat_models.py`.
- Preserved `server.Message`, `server.ChatRequest`, and `server.extract_system_prompt` as module-level imports for existing tests and callers.
- Verification:
  - `python -m py_compile server.py chat_models.py server_lifespan.py`: passed.
  - `python -m pytest tests/test_chat_models.py tests/test_prompt_memory_recall.py tests/test_stream_footer.py tests/test_access_guard.py tests/test_anthropic_tool_protocol.py -q --ignore=active_model`: `20 passed`.
  - `python -m pytest tests/test_agent_task_routes.py tests/test_access_guard.py tests/test_prompt_memory_recall.py tests/test_stream_footer.py tests/test_chat_models.py -q --ignore=active_model`: `40 passed`.
- VPS deployment:
  - backup `/opt/lima-router/backups/chat-models-extract-20260524_113220`;
  - uploaded `server.py` and `chat_models.py`;
  - remote `py_compile` and `import server; import chat_models` passed;
  - `systemctl restart lima-router` returned active.
- Public smokes:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `deploy_https_ok_1134`;
  - FRP chat returned exact `lima-chat-models-frp-ok`;
  - `/agent/worker/preflight` returned `ready=true`, latest task `cfcd3f2b`.

## 2026-05-24 Chat Request Helper Extraction Deploy

- Added regression contract `tests/test_chat_request_utils.py`.
- Extracted shared request-body helpers into `chat_request_utils.py`:
  - `extract_system_preview()` handles OpenAI `system` messages and Anthropic `system` strings/text blocks.
  - `extract_last_user_text()` handles string content and text blocks while ignoring image blocks.
- Replaced duplicate helper loops in the OpenAI `/v1/chat/completions` and Anthropic `/v1/messages` handlers without changing routing policy.
- Verification:
  - `python -m py_compile server.py chat_request_utils.py chat_models.py server_lifespan.py`: passed.
  - `python -m pytest tests/test_chat_models.py tests/test_prompt_memory_recall.py tests/test_stream_footer.py tests/test_access_guard.py tests/test_anthropic_tool_protocol.py tests/test_vision_routing.py -q --ignore=active_model`: `22 passed`.
  - `python -m pytest tests/test_agent_task_routes.py tests/test_access_guard.py tests/test_prompt_memory_recall.py tests/test_stream_footer.py tests/test_chat_models.py tests/test_chat_request_utils.py -q --ignore=active_model`: `45 passed`.
- VPS deployment:
  - backup `/opt/lima-router/backups/chat-request-utils-20260524_114403`;
  - uploaded `server.py` and `chat_request_utils.py`;
  - remote `py_compile` and `import server; import chat_request_utils` passed;
  - `systemctl restart lima-router` returned active.
- Public smokes:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `request_utils_https_ok`;
  - FRP chat returned exact `request_utils_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, latest task `cfcd3f2b`.

## 2026-05-24 Backend Registry And Key-Pool Deploy

- Closed the backend config/key-pool architecture backlog:
  - `backends.py` now owns shared proxy/capability sets and helper predicates.
  - `smart_router.py` uses `backends.GFW_BACKENDS` instead of a local duplicate.
  - `context_pipeline/reflection.py` uses the shared backend capability helpers instead of stale local sets.
  - `http_caller.py` now selects provider keys through `key_pool.py` and reports success/failure back to the pool.
  - `key_pool.py` can bootstrap provider pools from `LIMA_KEY_POOL_<PROVIDER>` with comma, semicolon, or newline separated keys and optional weights.
- Verification:
  - `python -m pytest tests/test_backend_registry.py test_http_caller.py tests/test_reflection.py tests/test_phase26_28.py -q --ignore=active_model`: `58 passed`.
  - `python -m py_compile backends.py smart_router.py http_caller.py key_pool.py context_pipeline/reflection.py server.py`: passed.
  - Expanded runtime regression: `110 passed`.
  - Secret/request/vision/free-web admission suite: `10 passed`.
- VPS deployment:
  - runtime commit `659f484` deployed;
  - backup `/opt/lima-router/backups/backend-registry-keypool-20260524-120642`;
  - uploaded `backends.py`, `smart_router.py`, `http_caller.py`, `key_pool.py`, and `context_pipeline/reflection.py`;
  - remote `py_compile` and `import server; import backends; import http_caller; import key_pool; import smart_router` passed;
  - `systemctl restart lima-router` returned active.
- Public smokes:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `backend_registry_https_ok`;
  - FRP chat returned exact `backend_registry_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.

## 2026-05-24 Endpoint And Key-Pool Telemetry Closure Deploy

- Closed the remaining concrete architecture items:
  - extracted OpenAI and Anthropic HTTP adapters into `routes/chat_endpoints.py`;
  - extracted models, health, live-key, and status endpoints into `routes/system_endpoints.py`;
  - retained `server.chat_completions`, `server.anthropic_messages`, and system endpoint aliases for compatibility;
  - reduced `server.py` to app setup plus core runtime helpers, with no direct business endpoint decorators;
  - added `key_pool.pool_snapshot()` with redacted key IDs and active/cooled/blocked status telemetry.
- Added regression coverage:
  - `tests/test_chat_endpoints.py`;
  - `tests/test_system_endpoints.py`;
  - `tests/test_key_pool.py`.
- Verification:
  - endpoint/key-pool focused regression: `62 passed`;
  - expanded runtime/admission/security regression: `128 passed`;
  - local `py_compile` passed for `server.py`, the extracted endpoint modules, and backend/key-pool runtime files.
- VPS deployment:
  - runtime commit `d10ed57`;
  - backup `/opt/lima-router/backups/endpoints-keypool-closed-20260524-123145`;
  - remote `py_compile` and import smoke passed;
  - `systemctl restart lima-router` returned active.
- Public smokes:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `endpoints_closed_https_ok`;
  - FRP chat returned exact `endpoints_closed_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.

## 2026-05-24 TechSpar Mastery Loop Closure

- Implemented the TechSpar-inspired local evidence loop:
  - `mastery_loop/models.py` defines mastery events, module mastery, weak points, review schedules, and recommendations.
  - `mastery_loop/profile_store.py` stores sanitized evidence in SQLite and redacts secret-like text before persistence.
  - `mastery_loop/event_adapter.py`, `weak_point_extractor.py`, `scorer.py`, `scheduler.py`, `recommender.py`, and `trace.py` convert tests/reviews/routes/tools/deploys into scores, weak points, schedules, and recommendation traces.
- Wired agent skill promotion to evidence:
  - `CandidateSkill` now stores `mastery_evidence_refs`.
  - `promote_candidate()` requires eval pass, manual approval, and non-empty mastery evidence refs before activation.
  - `/agent/skills/{skill_id}/promote` enforces the same gate.
  - Successful promotion is persisted back to the JSON candidate store.
- Added reference-boundary docs:
  - `docs/reference/TECHSPAR_BORROWING_NOTES.md`.
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`.
  - `docs/reference/POTPIE_COMPOSIO_BORROWING_NOTES.md` now also records AnySearch and FreeDomain boundaries.
- Updated status docs so stale claims no longer describe retrieval as compute-only or the TechSpar loop as only future work.
- Focused verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile mastery_loop\*.py agent_evolution\candidates.py agent_evolution\promote.py routes\agent_tasks.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests/test_mastery_loop.py tests/test_agent_evolution.py tests/test_agent_task_routes.py -q --ignore=active_model`: `40 passed`.
  - Expanded runtime regression over backend registry, key pool, endpoint, agent route, access, prompt-memory, routing, request-stats, vision, secret hygiene, mastery, and evolution tests: `144 passed`.
  - Focused docs/reference secret scan: no matches.
  - `git diff --check` on touched files: no whitespace errors; Git reported expected LF-to-CRLF working-copy warnings only.
- Remaining items are intentionally gated policy surfaces, not unimplemented migration tasks:
  - always-on worker daemon;
  - Kimi/TheOldLLM/MiMo/page-only promotion;
  - refresh execution;
  - mastery admin UI exposure and hot-path planner/routing influence.
- GitHub:
  - committed and pushed `bd0bf04` (`feat: add mastery loop evidence gates`) to `origin/codex/free-web-ai-probe`.
- VPS deployment:
  - backup `/opt/lima-router/backups/mastery-loop-20260524-125511`;
  - uploaded `mastery_loop/`, `agent_evolution/candidates.py`, `agent_evolution/promote.py`, and `routes/agent_tasks.py`;
  - remote `py_compile` and import smoke passed;
  - `systemctl restart lima-router` returned active.
- Public smokes after deployment:
  - `/health` returned `status=ok`;
  - HTTPS chat returned exact `mastery_loop_https_ok`;
  - FRP chat returned exact `mastery_loop_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.

## 2026-05-24 Online Distribution Governance

- User clarified that the VPS official website, open platform, and chat interface are LiMa distributions and must be controlled and recorded in the main repo/GitHub.
- Added distribution source of truth:
  - `docs/ONLINE_DISTRIBUTIONS.md`.
  - `infra/vps/nginx/chat.donglicao.com.conf`.
  - `infra/vps/nginx/api.donglicao.com.conf`.
  - `infra/vps/nginx/www.donglicao.com.conf`.
  - `infra/vps/systemd/lima-router.service`.
  - `infra/vps/systemd/lima-voice.service`.
  - `scripts/smoke_online_distributions.py`.
- Recorded active online surfaces:
  - official website: `https://www.donglicao.com` and `https://donglicao.com`;
  - chat/API: `https://chat.donglicao.com`;
  - open platform: `https://api.donglicao.com`;
  - FRP validation path: `http://47.112.162.80:8088`.
- Found and closed VPS service-file secret hygiene issue:
  - provider-key-like environment lines were present in `lima-router.service` and `lima-voice.service`;
  - migrated them into `/opt/lima-router/.env` and `/opt/lima-voice/.env`;
  - added `EnvironmentFile=/opt/lima-voice/.env`;
  - moved secret migration backups to `/root/secure-service-backups` with mode `600`;
  - `lima-router` and `lima-voice` restarted active;
  - `systemctl cat` no longer reports key/token/secret-like service lines.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile scripts\smoke_online_distributions.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe scripts\smoke_online_distributions.py --chat-exact distribution_control_ok`: `10/10 checks passed`.

## 2026-05-24 Reference Migration Compatibility Closure

- Closed the two remaining literal compatibility gaps from the reference migration audit:
  - added `code_context/retriever.py` as the planned Potpie-inspired retrieval facade over `InMemoryCodeIndex`;
  - added `docs/OPS_ENTRYPOINTS.md` as the original FreeDomain-inspired ops entrypoint document, pointing to the expanded `docs/ONLINE_DISTRIBUTIONS.md` source of truth.
- Added regression coverage that imports and uses `code_context.retriever.retrieve_relevant_files()`.

## 2026-05-24 LiMa Code Main-Repo Management Closure

- Registered `deepcode-cli` as the main repository's tracked LiMa Code submodule.
- Added `docs/LIMACODE_MANAGEMENT.md` as the governance record for LiMa Code ownership boundaries, submodule pointer updates, verification, and safety rules.
- Recorded LiMa Code as a first-class managed LiMa distribution in `STATUS.md` and `docs/DOCUMENTATION_STATUS.md`.

## 2026-05-24 esp32S_XYZ Backend Management Closure

- Registered `esp32S_XYZ` as the main repository's tracked downstream product submodule.
- Added `docs/ESP32S_XYZ_MANAGEMENT.md` as the governance record for LiMa backend ownership, product repository boundaries, submodule pointer updates, verification, and hardware-release safety rules.
- Recorded `esp32S_XYZ` as a first-class LiMa-managed product distribution in `STATUS.md`, `docs/DOCUMENTATION_STATUS.md`, and `docs/LIMA_MEMORY.md`.

## 2026-05-24 esp32S_XYZ Optimization Authorization

- Confirmed `D:\GIT\esp32S_XYZ` is a clean local clone of `https://github.com/zhuguang-ZFG/esp32S_XYZ.git` on `main...origin/main`.
- Recorded user authorization for LiMa to perform deep optimization and necessary refactoring in the product repository.
- Added `docs/ESP32S_XYZ_OPTIMIZATION_ROADMAP.md` and expanded `docs/ESP32S_XYZ_MANAGEMENT.md` with refactor authority, cross-repo order, and gated-release safeguards.

## 2026-05-24 LiMa Direct Device Gateway Plan

- User selected the long-term clean path: U8 firmware directly speaks a LiMa custom protocol and no longer depends on Xiaozhi server at runtime.
- Decided LiMa needs a new Device Gateway route layer (`/device/v1/*`) while continuing to reuse the existing model routing/provider stack.
- Added `docs/superpowers/plans/2026-05-24-lima-direct-device-gateway.md` with phased cross-repo implementation, protocol v1 message shapes, safety gates, and verification matrix.

## 2026-05-24 Xiaozhi Server Deprecation Plan

- User agreed to plan retirement of Xiaozhi server code after LiMa Direct Device Gateway replaces the runtime path.
- Added `docs/superpowers/plans/2026-05-24-xiaozhi-server-deprecation-removal.md`.
- Plan policy: mark as legacy first, build migration inventory, port useful behavior to LiMa direct route, verify fake U8 and real U8/U1 safety gates, then quarantine or delete and advance the main submodule pointer.

## 2026-05-24 Voice Display Companion Hardware References

- User requested that ElatoAI and the ESP32 TFT transparent-TV article be
  included in the later LiMa voice/display/companion hardware route.
- Added `docs/reference/HARDWARE_COMPANION_REFERENCES.md`.
- Updated the LiMa Direct Device Gateway plan, `esp32S_XYZ` optimization
  roadmap, documentation status, and durable memory to keep writing-machine
  direct control as the first target while admitting voice/display/companion
  devices as post-gate roadmap inputs.

## 2026-05-24 External Capability Radar And Adoption Roadmap

- User provided 27 external references for improving the main repo and
  subrepos.
- Added `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md` with
  capability groups, target repos, license signals, and priority candidates.
- Added
  `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`
  with staged adoption across code intelligence, memory, agent orchestration,
  sandbox/browser verification, research/trend products, persona/style, and
  hardware companions.
- Updated `docs/DOCUMENTATION_STATUS.md` and `docs/LIMA_MEMORY.md`.
- Current policy: concept-first, no automatic dependency adoption, and no code
  copy from GPL/AGPL/missing-license sources without a separate review gate.
- Added `NVIDIA/personaplex` to the persona, voice, and companion-device
  reference track as a realtime full-duplex speech/persona model candidate,
  gated by model license, privacy, safety, compute, and opt-in requirements.

## 2026-05-24 LiMa Device Gateway Implementation Slice

- Implemented the first code slice for LiMa-native device routing:
  - `device_gateway/protocol.py`;
  - `device_gateway/auth.py`;
  - `device_gateway/sessions.py`;
  - `device_gateway/intent.py`;
  - `device_gateway/safety.py`;
  - `device_gateway/tasks.py`;
  - `routes/device_gateway.py`;
  - `server.py` router registration.
- Added tests for protocol validation, deterministic command mapping, bounded
  fake `run_path` projection, `/device/v1/health`, `/device/v1/ws`, fake U8
  hello/heartbeat/transcript/motion_event loop, private HTTP event ingest,
  private debug task creation, and stable error envelopes.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile server.py routes\device_gateway.py device_gateway\protocol.py device_gateway\auth.py device_gateway\sessions.py device_gateway\tasks.py device_gateway\intent.py device_gateway\safety.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py -q --ignore=active_model`: 15 passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_system_endpoints.py tests\test_chat_endpoints.py tests\test_agent_task_routes.py -q --ignore=active_model`: 31 passed.

## 2026-05-24 esp32S_XYZ Fake LiMa U8 Client

- Implemented and pushed product-side fake LiMa U8 client:
  - product repo: `D:\GIT\esp32S_XYZ`;
  - commit: `78a62c9 test: add fake lima u8 client`;
  - remote: `https://github.com/zhuguang-ZFG/esp32S_XYZ.git`.
- Added `tools/fake_lima_u8/app.py` and unit tests using an in-memory transport
  so default product CI does not require a WebSocket dependency.
- Updated `tools/README.md`.
- Product verification:
  - `python -m py_compile tools\fake_lima_u8\app.py`: passed;
  - `python -m unittest tools.fake_lima_u8.tests.test_app -v`: 5 passed;
  - `python -m unittest tools.fake_device_server.tests.test_app tools.fake_ai.tests.test_app tools.fake_u1.tests.test_app -v`: 31 passed;
  - `python tools\validate_schemas.py`: `validated=62 passed=62 failed=0`.
- Main repo advanced the `esp32S_XYZ` submodule pointer to `78a62c9` and added
  `LIMA_DEVICE_TOKENS` to `.env.example`.

## 2026-05-24 Device Gateway Concurrency

- User asked whether LiMa routing supports concurrency and multiple devices /
  multiple requests at the same time.
- Implemented explicit concurrency support for the Device Gateway:
  - locked session registry;
  - per-session async send lock;
  - locked task store and task ID generation;
  - per-device offline task queues;
  - device `hello` flushes only that device's queued tasks;
  - `/device/v1/tasks` sends immediately to online devices or records queued
    state for offline devices;
  - `/device/v1/health` reports total pending tasks.
- Added `tests/test_device_gateway_concurrency.py`.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py tests\test_device_gateway_concurrency.py -q --ignore=active_model`: 19 passed.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile routes\device_gateway.py device_gateway\sessions.py device_gateway\tasks.py`: passed.
