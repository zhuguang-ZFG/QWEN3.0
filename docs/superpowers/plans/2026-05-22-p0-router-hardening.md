# P0 Router Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-risk LiMa router gaps found in the audit: private access boundaries, fallback context loss, and client-visible routing metadata leakage.

**Architecture:** Add a focused `access_guard.py` module for private API key parsing and FastAPI enforcement. Wire it only into public/private-sensitive HTTP entry points, keep `/health` and `/v1/models` public for smoke checks, and update fallback retry helpers to preserve the original message list.

**Tech Stack:** Python 3, FastAPI, pytest, existing LiMa router modules.

---

### Scope

- Protect `/v1/chat/completions` and `/v1/messages` with a bearer or raw API key.
- Protect `/api/live-key` and `/v1/status` with the same private key guard.
- Keep `/health` and `/v1/models` unauthenticated for uptime and IDE model discovery.
- Make `/admin/*` fail closed when `LIMA_ADMIN_TOKEN` is not configured.
- Preserve full `messages` during same-tier and upgrade fallback retries.
- Keep selected backend names in internal request evidence only, not in streamed client text.
- Make the existing async streaming regression tests run in the local pytest environment without relying on an unconfigured pytest plugin.

### Non-Goals

- No commercial billing, user signup, paid quota, or dashboard work.
- No MAB routing, plugin architecture, semantic embedding model, or YAML routing rewrite in this increment.
- No VPS deployment in this pass unless explicitly requested after local verification. The user later explicitly requested deployment, so a separate deployment pass was executed after local verification.

### Implementation Tasks

- [x] Add tests for API key parsing and request authorization in `tests/test_access_guard.py`.
- [x] Add tests for admin fail-closed behavior in `tests/test_access_guard.py`.
- [x] Add a regression test proving `_try_backend(..., messages=full_messages)` forwards complete context in `tests/test_fallback_context.py`.
- [x] Add a regression test proving ordinary chat messages do not produce a truthy IDE source.
- [x] Add regression tests proving image generation is private-key protected and rejects oversized image dimensions.
- [x] Implement `access_guard.py` with `configured_api_keys()`, `is_private_access_configured()`, and `require_private_api_key()`.
- [x] Wire `require_private_api_key` into `server.py` private endpoints.
- [x] Change `routes/admin.py` so missing `LIMA_ADMIN_TOKEN` returns a configuration error instead of allowing access.
- [x] Extend `_try_backend()` to accept optional full messages and update fallback call sites.
- [x] Change `_detect_ide()` to return an empty string for ordinary messages.
- [x] Protect `/v1/images/generations` with the private key guard and cap dimensions at 2048x2048.
- [x] Add regression tests proving Anthropic stream text does not append a backend footer.
- [x] Remove client-visible backend footers from Anthropic speculative and fake stream paths.
- [x] Convert `test_streaming.py` async tests to synchronous `asyncio.run()` wrappers so they execute instead of skipping.
- [x] Run focused tests and core routing regression suite.

### Verification Commands

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_access_guard.py tests\test_fallback_context.py -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_stream_footer.py -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m pytest test_streaming.py tests\test_stream_footer.py -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py test_http_caller.py test_rate_limiter.py test_streaming.py tests\test_coding_eval.py tests\test_lima_context.py tests\test_anthropic_tool_protocol.py tests\test_route_scorer.py tests\test_free_web_ai_probe.py tests\test_free_web_ai_admission.py tests\test_access_guard.py tests\test_fallback_context.py tests\test_ide_detection.py tests\test_image_endpoint_guard.py tests\test_stream_footer.py -q --ignore=active_model
```

Latest local result after streaming-test cleanup: `112 passed`; the previous 5 skipped async streaming tests now execute through `asyncio.run()`.

### Deployment Evidence

- GitHub push: commit `c4515d3` to `origin/codex/free-web-ai-probe`.
- P0 runtime backup: `/opt/lima-router/backups/p0-router-hardening-20260522_230407`.
- Uploaded runtime files: `server.py`, `access_guard.py`, and `routes/admin.py`.
- Added `LIMA_API_KEY` to remote `.env` because no private API key was configured and the new guard fails closed.
- Remote compile passed for `server.py`, `access_guard.py`, and `routes/admin.py`.
- Synced stale remote `health_tracker.py` after authorized endpoints returned 500:
  - Backup: `/opt/lima-router/backups/health-tracker-sync-20260522_230937`.
  - Root cause: remote `health_tracker.py` lacked `get_backend_state()` required by `routing_engine.py`.
  - Remote compile passed for `health_tracker.py`, `routing_engine.py`, `server.py`, `access_guard.py`, and `routes/admin.py`.
- Public smoke:
  - `/v1/chat/completions` without auth returned 401.
  - `/v1/chat/completions` with auth returned exact `p0-deploy-ok`.
  - `/v1/messages` with auth returned exact `p0-msg-ok`.
  - FRP `/health` returned 200.

### Rollback

- Remove `access_guard.py`.
- Remove the `Depends(require_private_api_key)` dependencies from `server.py`.
- Restore `routes/admin.py` empty-token behavior only if a local-only development environment explicitly requires it.
- Revert `_try_backend()` signature and fallback call-site changes.
