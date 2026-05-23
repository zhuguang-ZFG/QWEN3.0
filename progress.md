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
- Calibrated module status:
  - Session Memory writes and compaction trigger are in the successful chat path.
  - Session Memory recall processor exists but is not the main `server.py` prompt-time path.
  - Graph retrieval/reranking is computed but not yet injected into prompt context.
  - Tool Gateway executor is hardened with `shell=False`, audit events, and copied HTTP args.
  - Admin UI auth is improved, but query-token login remains a later hardening target.
  - `ConcurrencyPool` exists and is tested, but key scheduling has not been replaced.
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
